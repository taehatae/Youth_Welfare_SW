"""Recommendation decisions are separate from Policy B.

The job, ranking and medical excerpts are public DB text checked on 2026-10-30.
All profiles and the other clauses are synthetic. No production DB/network.
"""
import pytest

from app.models.user import User
from app.models.welfare_service import WelfareService
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition as Condition
from app.schemas.welfare import EligibilityAnalysis
from app.services.eligibility_condition_service import EligibilityConditionService as Parser
from app.services.eligibility_matching_service import EligibilityMatchingService as Matcher


JOB = (
    "18세 이상 「장애인복지법」상 등록된 미취업 장애인을 대상으로 합니다."
    "* 일자리 지원 주요직무 : 행정도우미, 전담지원 행정도우미, 복지서비스 지원요원 등"
)
SCORE = "1. 연령(30점) : 청년 30점(34세 이하), 비청년 20점(35세), 19점(36세) … 1점(54세 이상)"
MEDICAL = (
    "주민등록상 사업지역(19개 시군구)에 거주하는 30세 이상 고혈압·당뇨병 환자를 대상으로 합니다. "
    "※ 의료비(진료비 및 약제비) 지원 대상 : 65세 이상 고혈압, 당뇨병 환자"
)


def analyze(text, disability="NO", age=25, employment="UNEMPLOYED", selection="", rows=None):
    user = User(age=age, region="서울특별시 관악구", income_level=1234567,
                employment_status=employment)
    service = WelfareService(serv_id="test", serv_name="Test", detail_url="",
                             target_details=text, selection_criteria=selection)
    conditions = rows if rows is not None else [
        Condition(serv_id="test", **item) for item in Parser.structure_service(text, selection)
    ]
    return Matcher().analyze_service(user, service, conditions,
                                    {"disability_status": disability})


@pytest.mark.parametrize("value,decision", [
    ("NO", "excluded"), ("YES", "candidate"), ("UNKNOWN", "unverified"), (None, "unverified"),
])
def test_synthetic_verified_registration_gate(value, decision):
    result = analyze("등록장애인을 지원합니다.", value)
    assert result["recommendation_decision"] == decision
    assert result["decision_reason"]
    assert result["decision_warnings"]
    assert len(result["decision_evidence"]) == 1
    evidence = result["decision_evidence"][0]
    assert evidence["role"] == "requirement"
    assert evidence["subject"] == "applicant"
    assert evidence["scope"] == "program"
    assert evidence["input_fields"] == ["eligibility_conditions.disability_status"]
    assert evidence["source_field"] == "target_details"
    assert evidence["source_text"] == "등록장애인을 지원합니다."
    assert EligibilityAnalysis.model_validate(result).model_dump() == result


@pytest.mark.parametrize("value,decision", [("NO", "excluded"), ("YES", "candidate")])
def test_actual_job_proof_with_unknown_details_preserves_policy_b(value, decision):
    result = analyze(JOB, value)
    assert result["recommendation_decision"] == decision
    assert result["status"] == "needs_review"
    assert result["review_conditions"]
    assert len(result["gap_conditions"]) == int(value == "NO")
    assert result["match_score"] == (66.7 if value == "NO" else 100)


@pytest.mark.parametrize("value,decision", [("NO", "excluded"), ("YES", "candidate")])
def test_synthetic_unrelated_review_does_not_erase_verified_proof(value, decision):
    result = analyze("등록장애인을 지원합니다.\n추가 서류 심사가 필요합니다.", value)
    assert result["recommendation_decision"] == decision
    assert result["review_conditions"]
    assert result["status"] == "needs_review"


@pytest.mark.parametrize("source", [
    "등록장애인의 가족을 지원합니다.",
    "등록장애인의 보호자를 지원합니다.",
    "등록장애인은 선발 시 우대합니다.",
    "등록장애인 또는 의사의 소견으로 인정된 사람을 지원합니다.",
    "등록장애인을 지원합니다.\n다만 미등록 장애인도 별도 인정 시 신청할 수 있습니다.",
    "다음 사항 중 어느 하나\n등록장애인\n의사가 인정한 사람",
    "세부 지원 대상\n등록장애인",
    "보호자 자격\n등록장애인",
    "우대 기준\n등록장애인",
    "신청일 기준\n등록장애인",
])
def test_synthetic_unresolved_subject_scope_time_or_alternative_cannot_exclude(source):
    result = analyze(source)
    assert result["recommendation_decision"] == "unverified"
    assert not any(e["decision_usable"] and e["comparison_result"] == "failed"
                   for e in result["decision_evidence"])


def test_synthetic_age_pass_does_not_override_unresolved_registration_alternative():
    result = analyze("만 19세 이상\n등록장애인 또는 별도 인정 대상자")
    assert result["recommendation_decision"] == "unverified"


@pytest.mark.parametrize("source,age", [(SCORE, 25), (MEDICAL, 40),
    ("만 18세 이하 자녀를 양육하고 있는 보호자를 지원합니다.", 25)])
def test_public_roles_and_synthetic_child_age_are_not_service_exclusion(source, age):
    result = analyze(source, age=age)
    assert result["recommendation_decision"] != "excluded"
    if source == SCORE:
        assert result["recommendation_decision"] == "unverified"
    if "자녀" in source:
        age_evidence = next(e for e in result["decision_evidence"] if e["condition_type"] == "age")
        assert age_evidence["subject"] == "child"
        assert age_evidence["input_fields"] == []


@pytest.mark.parametrize("age,decision", [(18, "excluded"), (19, "candidate"), (30, "candidate")])
def test_synthetic_exclusion_direction_is_a_gate_not_a_positive_age_requirement(age, decision):
    result = analyze("만 19세 미만은 참여가 불가합니다.", age=age)
    assert result["recommendation_decision"] == decision
    assert result["decision_evidence"][0]["role"] == "exclusion"


def test_synthetic_legacy_age_without_original_proof_is_not_promoted():
    row = Condition(serv_id="test", condition_type="age", operator="gte", value_number=19,
                    value_text="만 19세 이상", unit="세", comparison_ready=True,
                    parse_status="parsed", source_field="target_details", source_text="만 19세 이상")
    result = analyze("", age=18, rows=[row])
    assert result["status"] == "ineligible"  # Existing outcome is untouched.
    assert result["recommendation_decision"] == "unverified"


def test_synthetic_tampered_legacy_numeric_value_is_not_verified_proof():
    row = Condition(serv_id="test", condition_type="age", operator="gte", value_number=99,
                    value_text="만 19세 이상", unit="세", comparison_ready=True,
                    parse_status="parsed", source_field="target_details", source_text="만 19세 이상")
    result = analyze("만 19세 이상", rows=[row])
    assert result["recommendation_decision"] == "unverified"


def test_no_comparison_does_not_mean_candidate():
    result = analyze("담당 기관의 추가 확인이 필요합니다.")
    assert result["recommendation_decision"] == "unverified"


def test_evidence_never_copies_private_input_into_new_keys_or_logs(caplog, capsys):
    result = analyze("등록장애인을 지원합니다.")
    assert "1234567" not in str(result["decision_evidence"])
    assert "관악구" not in str(result["decision_evidence"])
    assert "current_value" not in str(result["decision_evidence"])
    assert "등록장애인" not in caplog.text
    assert capsys.readouterr().out == ""


def test_saved_legacy_analysis_without_new_fields_still_validates():
    result = analyze("만 19세 이상")
    for key in ("recommendation_decision", "decision_reason", "decision_warnings", "decision_evidence"):
        result.pop(key, None)
    old = EligibilityAnalysis.model_validate(result)
    assert old.recommendation_decision == "unverified"


@pytest.mark.parametrize("heading", ["세부 지원 대상", "보호자 자격", "우대 기준", "신청일 기준"])
def test_synthetic_parent_heading_also_applies_across_fields(heading):
    result = analyze(heading, selection="등록장애인")
    assert result["recommendation_decision"] == "unverified"


def test_synthetic_family_proof_preserves_subject_without_using_self_value():
    result = analyze("등록장애인의 가족을 지원합니다.")
    assert result["recommendation_decision"] == "unverified"
    assert any(item["subject"] == "family" for item in result["decision_evidence"])


@pytest.mark.parametrize("suffix", [
    "위 조건은 의료비 지원에만 적용합니다.",
    "위 조건은 우대 사항입니다.",
    "위 조건은 신청자의 자녀를 기준으로 확인합니다.",
])
def test_synthetic_following_qualification_cannot_be_detached_from_gate(suffix):
    result = analyze("등록장애인을 지원합니다.\n" + suffix)
    assert result["recommendation_decision"] == "unverified"


def test_synthetic_following_time_reference_is_not_current_age():
    result = analyze("만 19세 이상\n위 연령은 2020년 기준입니다.", age=18)
    assert result["recommendation_decision"] == "unverified"


@pytest.mark.parametrize("suffix", [
    "장애인 등록 여부는 필수 자격이 아닙니다.",
    "장애인 등록 여부는 가점 항목입니다.",
    "장애등록이 없는 사람도 지원받을 수 있습니다.",
    "등록장애인의 자녀도 신청 가능합니다.",
])
@pytest.mark.parametrize("field", ["target_details", "selection_criteria"])
def test_synthetic_following_qualification_requires_positive_independence(suffix, field):
    result = analyze("등록장애인을 지원합니다." + ("\n" + suffix if field == "target_details" else ""),
                     selection=suffix if field == "selection_criteria" else "")
    assert result["recommendation_decision"] == "unverified"


def test_synthetic_known_independent_household_detail_does_not_require_new_input():
    result = analyze("등록장애인을 지원합니다.\n가구원 수는 3인 이상이어야 합니다.", disability="YES")
    assert result["review_conditions"]
    assert result["recommendation_decision"] == "candidate"


def test_synthetic_bare_gate_followed_by_dependent_continuation_is_not_self():
    result = analyze("등록장애인\n의 자녀를 지원합니다.")
    assert result["recommendation_decision"] == "unverified"


@pytest.mark.parametrize("value,expected", [("NO", "excluded"), ("YES", "unverified"), ("UNKNOWN", "unverified")])
def test_actual_job_registration_failure_is_independent_of_employment_exceptions(value, expected):
    import json
    from pathlib import Path
    selection = json.loads((Path(__file__).parent / "fixtures" /
        "registered_job_selection_excerpt.json").read_text(encoding="utf-8"))["selection_criteria"]
    result = analyze(JOB, value, selection=selection)
    # YES alone cannot resolve the separate employment/other exceptions.
    assert result["recommendation_decision"] == expected
    registration = next(e for e in result["decision_evidence"]
                        if e["input_fields"] == ["eligibility_conditions.disability_status"])
    assert registration["decision_usable"] == (value in {"YES", "NO"})
    assert result["status"] == "needs_review"


def test_changed_job_selection_cannot_silently_inherit_verified_independence():
    import json
    from pathlib import Path
    selection = json.loads((Path(__file__).parent / "fixtures" /
        "registered_job_selection_excerpt.json").read_text(encoding="utf-8"))["selection_criteria"]
    result = analyze(JOB, selection=selection + "\n다만 미등록 장애인도 별도 인정 시 신청할 수 있습니다.")
    assert result["recommendation_decision"] == "unverified"


@pytest.mark.parametrize("footnote", [
    "미등록장애인도 지원 가능합니다.",
    "장애인 등록 여부는 가점 항목입니다.",
    "등록장애인의 자녀도 신청 가능합니다.",
])
@pytest.mark.parametrize("use_public_selection", [False, True])
def test_synthetic_internal_footnote_must_not_be_discarded_when_certifying_gate(footnote, use_public_selection):
    import json
    from pathlib import Path
    selection = json.loads((Path(__file__).parent / "fixtures" /
        "registered_job_selection_excerpt.json").read_text(encoding="utf-8"))["selection_criteria"] if use_public_selection else ""
    source = JOB.split("*", 1)[0] + "* " + footnote
    result = analyze(source, selection=selection)
    assert result["recommendation_decision"] == "unverified"


@pytest.fixture
def api_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from app.api.routes.auth import router as auth
    from app.api.routes.users import router as users
    from app.api.routes.welfare import router as welfare
    from app.database.connection import Base, create_database_engine, get_db

    engine = create_database_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as db:
        app = FastAPI()
        for router in (auth, users, welfare):
            app.include_router(router, prefix="/api/v1")

        def dependency():
            yield db

        app.dependency_overrides[get_db] = dependency
        db.add_all([
            WelfareService(serv_id="reg", serv_name="Registered", detail_url="",
                           target_details="등록장애인을 지원합니다.\n추가 서류 확인이 필요합니다."),
            WelfareService(serv_id="age", serv_name="Age", detail_url="", target_details="만 19세 이상"),
            WelfareService(serv_id="no-proof", serv_name="Unknown", detail_url="", target_details="별도 확인 필요"),
        ])
        db.commit()
        with TestClient(app) as client:
            assert client.post("/api/v1/auth/signup", json={"username": "decision_test",
                "password": "Regression123!", "display_name": "Test"}).status_code == 201
            yield client, db
    engine.dispose()


@pytest.mark.parametrize("value,expected", [("NO", "excluded"), ("YES", "candidate"), ("UNKNOWN", "unverified")])
def test_both_diagnosis_paths_and_saved_snapshot_use_same_decision(api_client, value, expected):
    import json
    from app.models.account import Account, AccountWorkspace
    client, db = api_client
    response = client.post("/api/v1/welfare/diagnose", json={
        "age": 25, "region": "서울특별시 관악구", "income_level": 1234567,
        "employment_status": "UNEMPLOYED", "eligibility_conditions": {"disability_status": value},
    })
    assert response.status_code == 200
    workspace = response.json()
    result = workspace["current"]["analysis"]["matched"]
    user_id = db.query(Account).one().profile_id
    matched = client.get("/api/v1/welfare/matched", params={"user_id": user_id})
    assert matched.status_code == 200
    assert matched.json()["analysis_results"] == result["analysis_results"]
    rows = {item["policy_id"]: item for item in result["analysis_results"]}
    assert rows["reg"]["recommendation_decision"] == expected
    assert rows["reg"]["status"] == "needs_review"
    assert {item["policy_id"] for item in result["policies"]} == {"age"}
    assert rows["no-proof"]["recommendation_decision"] == "unverified"
    assert "1234567" not in json.dumps(workspace, ensure_ascii=False)
    assert "관악구" not in json.dumps(workspace, ensure_ascii=False)
    assert db.query(AccountWorkspace).count() == 1
    # Re-loading the workspace also retains typed additive fields.
    saved = client.get("/api/v1/users/state")
    assert saved.status_code == 200
    assert saved.json()["current"]["analysis"]["matched"]["analysis_results"] == result["analysis_results"]
