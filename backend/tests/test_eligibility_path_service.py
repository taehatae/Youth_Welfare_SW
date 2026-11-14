import json
from types import SimpleNamespace

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.models.eligibility_path import COMMON_PATH, EligibilityPath, EligibilityPathCondition, PolicyEligibility
from app.models.welfare_service import WelfareService
from app.services import eligibility_path_service as paths
from app.services import structured_condition_service as structured

SERVICE = SimpleNamespace(serv_id="WLF-TEST", serv_name="테스트 진단서 지원", detail_url="https://example.test",
                          target_details="신규 등록이 필요한 수급자 / 재판정 장애인 중 수급자 또는 차상위", selection_criteria="")
USER = SimpleNamespace(age=22, region="서울특별시 동대문구", income_level=0, employment_status="UNEMPLOYED")


def profile(**extra):
    base = {"disability_status": "NO", "student_status": "YES", "owns_home": False, "household_size": 1,
            "additional_conditions": {"basic_benefit_status": "NO", "near_poverty_status": "YES", "nationality": "KOREAN",
                                    "special_targets": []}}
    base["additional_conditions"].update(extra.pop("additional", {}))
    return {**base, **extra}


def condition(field, op, value=None, upper=None, values=(), kind="requirement"):
    return EligibilityPathCondition(field=field, operator=op, value=value, upper_value=upper, values=list(values),
                                    kind=kind, evidence=f"{field} 근거")


def record(path_specs, common=(), common_checks=()):
    rec = PolicyEligibility(serv_id=SERVICE.serv_id, source_sha256=structured.source_hash(SERVICE), status="reviewed",
                            preferences=[])
    rec.paths = [EligibilityPath(path_key=COMMON_PATH, label="공통 조건", kind="공통", checks=list(common_checks),
                                 conditions=list(common))]
    for key, conditions, checks in path_specs:
        rec.paths.append(EligibilityPath(path_key=key, label=key, kind="기본", checks=list(checks),
                                         conditions=list(conditions)))
    return rec


def diagnosis_record():
    return record([
        ("신규등록", [condition("기초생활보장 수급자", "is_true"), condition("등록 장애인", "is_true", kind="exclusion")], []),
        ("재판정-수급", [condition("등록 장애인", "is_true"), condition("기초생활보장 수급자", "is_true")], ["재판정 시기"]),
        ("재판정-차상위", [condition("등록 장애인", "is_true"), condition("차상위계층", "is_true")], ["재판정 시기"]),
    ])


def test_non_disabled_near_poverty_is_ineligible_on_every_path():
    result = paths.analyze(SERVICE, USER, profile(), diagnosis_record())
    assert result["status"] == "ineligible"
    assert all(p["status"] == "ineligible" for p in result["eligibility_paths"])
    # 가장 가까운 경로(미충족 1개)를 역설계로 보여준다.
    assert result["matched_path_id"] in {"신규등록", "재판정-차상위"}
    assert len(result["gap_conditions"]) == 1


def test_disabled_near_poverty_passes_one_path_and_shows_its_checks():
    result = paths.analyze(SERVICE, USER, profile(disability_status="YES"), diagnosis_record())
    assert result["status"] == "eligible" and result["matched_path_id"] == "재판정-차상위"
    assert [r["required_value"] for r in result["review_conditions"]] == ["재판정 시기"]
    assert "'재판정-차상위' 경로" in result["recommendation_reason"]


def test_unknown_input_needs_review_not_ineligible():
    result = paths.analyze(SERVICE, USER, profile(disability_status="UNKNOWN", additional={"near_poverty_status": None}),
                           diagnosis_record())
    assert result["status"] == "needs_review"


def test_common_condition_block_is_reported_once():
    rec = record([("주택", [condition("세대원 전원 무주택", "is_true")], []), ("사업", [], ["사업 운영"])],
                 common=[condition("국가유공자·보훈대상자", "is_true")])
    result = paths.analyze(SERVICE, USER, profile(), rec)
    assert result["status"] == "ineligible" and result["blocked_by_common"] == ["국가유공자·보훈대상자"]
    assert [g["condition_type"] for g in result["gap_conditions"]] == ["국가유공자·보훈대상자"]


def test_path_without_comparable_conditions_keeps_policy_out_of_ineligible():
    rec = record([("소득", [condition("가구 소득인정액", "lte", 50)], []), ("심사", [], ["기관 심사"])])
    extra = {"recognized_household_income_won": 50_000_000}
    result = paths.analyze(SERVICE, USER, profile(additional=extra), rec)
    assert result["status"] == "needs_review"


def test_changed_source_falls_back():
    changed = SimpleNamespace(**{**vars(SERVICE), "target_details": "원문 변경"})
    assert paths.analyze(changed, USER, profile(), diagnosis_record()) is None
    assert paths.analyze(SERVICE, USER, profile(), None) is None


def test_seed_from_file_round_trip(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(WelfareService(serv_id=SERVICE.serv_id, serv_name=SERVICE.serv_name, detail_url=SERVICE.detail_url,
                          target_details=SERVICE.target_details, selection_criteria=""))
    db.commit()
    seed = tmp_path / "paths.json"
    seed.write_text(json.dumps({"version": 2, "policies": [{
        "serv_id": SERVICE.serv_id, "source_sha256": structured.source_hash(SERVICE), "status": "reviewed",
        "common": [{"field": "만 나이", "op": "gte", "value": 18}],
        "paths": [{"id": "기본", "label": "기본", "conditions": [{"field": "차상위계층", "op": "is_true"}]}]}]}),
        encoding="utf-8")
    assert paths.seed_from_file(db, seed) == 1
    assert paths.seed_from_file(db, seed) == 1  # 다시 넣어도 경로가 중복되지 않는다
    loaded = paths.load(db)[SERVICE.serv_id]
    assert [p.path_key for p in loaded.paths] == [COMMON_PATH, "기본"]
    assert paths.analyze(SERVICE, USER, profile(), loaded)["status"] == "eligible"
    db.close()


def test_seed_reload_removes_policies_dropped_from_seed(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    for sid in ("A", "B"):
        db.add(WelfareService(serv_id=sid, serv_name=sid, target_details="원문", selection_criteria=""))
    db.commit()
    item = lambda sid: {"serv_id": sid, "source_sha256": "x", "status": "reviewed",
                        "paths": [{"id": "기본", "label": "기본", "conditions": [{"field": "만 나이", "op": "gte", "value": 18}]}]}
    seed = tmp_path / "paths.json"
    seed.write_text(json.dumps({"version": 2, "policies": [item("A"), item("B")]}), encoding="utf-8")
    paths.seed_from_file(db, seed)
    # B가 재검수 대상이 되어 시드에서 빠지면 DB에서도 지운다(예전 경로가 남지 않는다).
    seed.write_text(json.dumps({"version": 2, "policies": [item("A")]}), encoding="utf-8")
    paths.seed_from_file(db, seed)
    assert [r.serv_id for r in db.query(PolicyEligibility)] == ["A"]
    assert db.query(EligibilityPath).count() == 2  # A의 공통 경로 + 기본 경로
    assert db.query(EligibilityPathCondition).count() == 1
    db.close()


def test_seed_file_covers_every_policy_with_known_fields():
    data = json.loads(paths.SEED_PATH.read_text(encoding="utf-8"))
    fields = set(structured.user_values(USER, profile()))
    assert len(data["policies"]) >= 95
    for policy in data["policies"]:
        assert policy["paths"], policy["serv_id"]
        for p in [{"conditions": policy.get("common", [])}] + policy["paths"]:
            for c in p.get("conditions", []):
                assert c["field"] in fields and c["op"] in {"gte", "lte", "between", "one_of", "is_true"}


def batch4_record(serv_id):
    """검수 데이터를 메모리 모델로만 구성한다. DB 적재는 하지 않는다."""
    data = paths.SEED_PATH.parent
    policy = next(p for p in json.loads((data / "eligibility_paths_reviewed.json").read_text(encoding="utf-8"))["policies"]
                  if p["serv_id"] == serv_id and p.get("batch") == 4)
    source = next(p for p in json.loads((data / "welfare-policies.json").read_text(encoding="utf-8"))["data"]["welfare_services"]
                  if p["serv_id"] == serv_id)
    service = SimpleNamespace(serv_id=serv_id, serv_name=policy["name"], detail_url=source.get("detail_url"),
                              target_details=source["target_details"], selection_criteria=source["selection_criteria"])

    def convert(c):
        result = condition(c["field"], c["op"], c.get("value"), c.get("upper"), c.get("values", []),
                           c.get("kind", "requirement"))
        result.evidence = c["evidence"]
        return result

    rec = record([(p["id"], [convert(c) for c in p["conditions"]], p["checks"]) for p in policy["paths"]],
                 common=[convert(c) for c in policy["common"]], common_checks=policy["common_checks"])
    rec.serv_id = serv_id
    rec.source_sha256 = structured.source_hash(service)
    return service, rec


@pytest.mark.parametrize("serv_id,age,provided,passed", [
    ("WLF00006269", 27, profile(), 1),
    ("WLF00003265", 19, profile(disability_status="YES", additional={"severe_disability": "NO"}), 4),
    ("WLF00006266", 35, {"household_size": 1, "additional_conditions": {"household_monthly_income_won": 2_000_000}}, 3),
])
def test_batch4_can_be_eligible_with_unverified_required_checks(serv_id, age, provided, passed):
    # 비교 조건을 모두 충족하면 가능. 확인 사항은 '추가 확인'으로만 남는다.
    service, rec = batch4_record(serv_id)
    user = SimpleNamespace(age=age, region=None, income_level=None if serv_id != "WLF00006266" else 2_000_000,
                           employment_status=None)

    result = paths.analyze(service, user, provided, rec)

    assert result["status"] == "eligible"
    assert result["passed_conditions"] == passed
    assert all(row["status"] == "needs_review" for row in result["review_conditions"])
    assert result["gap_conditions"] == []


@pytest.mark.parametrize("serv_id,provided,missing", [
    ("WLF00003265", profile(disability_status="YES"), "중증 장애인"),
    ("WLF00006266", {}, "본인 연소득"),
])
def test_batch4_recheck_asks_for_newly_comparable_inputs(serv_id, provided, missing):
    # 미충족 없이 충족한 조건이 있으면 가능. 입력하지 않은 기준은 불가로 만들지 않고 '추가 확인'으로 안내한다.
    service, rec = batch4_record(serv_id)
    user = SimpleNamespace(age=30, region=None, income_level=None, employment_status=None)

    result = paths.analyze(service, user, provided, rec)

    assert result["status"] == "eligible" and result["gap_conditions"] == []
    assert missing in result["recommendation_reason"]
    assert missing in {r["condition_type"] for r in result["review_conditions"]}


def test_path_status_rule_met_without_unmet_is_eligible():
    # 미충족 있음 → 불가, 미충족 없고 충족 있음 → 가능, 충족·미충족 모두 없음 → 확인 필요
    rec = record([("기본", [condition("만 나이", "gte", 19), condition("등록 장애인", "is_true")], [])])
    adult = SimpleNamespace(age=22, region=None, income_level=None, employment_status=None)
    minor = SimpleNamespace(age=17, region=None, income_level=None, employment_status=None)
    unknown = SimpleNamespace(age=None, region=None, income_level=None, employment_status=None)
    unanswered = {"disability_status": "UNKNOWN"}

    assert paths.analyze(SERVICE, adult, unanswered, rec)["status"] == "eligible"
    assert paths.analyze(SERVICE, minor, unanswered, rec)["status"] == "ineligible"
    assert paths.analyze(SERVICE, unknown, unanswered, rec)["status"] == "needs_review"
    assert paths.analyze(SERVICE, adult, {"disability_status": "NO"}, rec)["status"] == "ineligible"


def test_batch4_paths_without_comparison_conditions_remain_needs_review():
    checked = 0
    for serv_id in ("WLF00001146", "WLF00003231", "WLF00006269"):
        _, rec = batch4_record(serv_id)
        common = rec.paths[0]
        for path in rec.paths[1:]:
            if common.conditions or path.conditions:
                continue
            result = paths._evaluate_path(path, common, {})
            assert result["status"] == "needs_review"
            assert result["conditions"] == []
            checked += 1
    # 재검수 후 보조공학기기 3개·미소금융 수급권자 경로가 비교 조건을 갖게 됐다.
    assert checked == 5
