"""간편 정책 찾기: 분야를 고르고 그 분야 정책이 실제로 비교하는 조건만 입력받아, 기존 판정 엔진으로 평가한다.

- 판정은 EligibilityMatchingService.analyze_user를 그대로 쓴다(새 판정 규칙 없음). 결과를 분야로 거를 뿐이다.
- 입력하지 않은 값은 프로필에 넣지 않는다. 0·미혼·대한민국 같은 기본값을 채우지 않아 엔진이 '미입력 → 확인 필요'로 처리한다.
- 사용자·프로필·워크스페이스·진단 스냅샷을 저장하지 않는다. User는 세션에 붙이지 않은 임시 객체다.
- 응답은 기존 공개 투영(hide_input_values)으로 정확한 난이도·evaluation_context·입력값을 가린다.
- 공개 API는 읽기 전용이다. 경로 데이터가 비었거나 일부만 적재됐으면 503으로 멈춘다(엔진 load()의 자동 시드 적재에 닿지 않게).
"""
import json
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.eligibility_path import COMMON_PATH, EligibilityPath, EligibilityPathCondition, PolicyEligibility
from app.models.user import User
from app.models.welfare_service import WelfareService
from app.schemas.quick_finder import (
    QuickAnswers, QuickCategoriesResponse, QuickCategory, QuickCategoryDetail, QuickEvaluateResponse, QuickField,
)
from app.schemas.welfare import MatchedPoliciesResponse
from app.services import structured_condition_service as base
from app.services.eligibility_condition_service import EligibilityConditionService
from app.services.eligibility_matching_service import EligibilityMatchingService
from app.services.policy_catalog_service import CATEGORIES, categories_of
from app.services.profile_privacy import hide_input_values

# 질문(입력 카드) → 받는 입력 항목. 화면 frontend/src/features/quick/quickQuestions.ts와 같은 id를 쓴다.
QUESTIONS: dict[str, tuple[str, ...]] = {
    "age": ("age",),
    "region": ("region",),
    "income": ("income_monthly_won",),
    "employment": ("employment",),
    "gender": ("gender",),
    "household": ("household_size",),
    "household_income": ("household_monthly_income_won",),
    "recognized_income": ("recognized_household_income_won",),
    "household_assets": ("asset_amount_won", "household_debt_won"),
    "personal_assets": ("personal_asset_amount_won", "personal_debt_won"),
    "car": ("car_value_won",),
    "housing_type": ("housing_type",),
    "home_ownership": ("owns_home", "household_homeless"),
    "disability": ("disability_status", "severe_disability"),
    "student": ("student_status", "school_level"),
    "marriage": ("marital_status", "marriage_years", "spouse_monthly_income_won"),
    "children": ("children_count", "youngest_child_age"),
    "pregnancy": ("pregnancy",),
    "nationality": ("nationality",),
    "special_targets": ("special_targets",),
    "basic_benefit": ("basic_benefit_status", "basic_benefit_types", "household_basic_benefit_status"),
    "near_poverty": ("near_poverty_status",),
    "single_parent": ("single_parent_support_status",),
    "job_seek": ("job_seek_registration",),
    "protection": ("child_welfare_protection_experience", "protection_ended"),
    "credit": ("credit_bureau", "credit_score"),
}

# 경로 비교 조건 항목 → 그 값을 계산하는 데 필요한 질문. structured_condition_service.user_values의 계산식을 따른다.
FIELD_QUESTIONS: dict[str, tuple[str, ...]] = {
    "만 나이": ("age",),
    "거주지": ("region",),
    "본인 월소득": ("income",),
    "본인 연소득": ("income",),
    "고용 상태": ("employment",),
    "성별": ("gender",),
    "가구원 수": ("household",),
    "부모와 따로 거주": ("household",),
    "가구 소득인정액": ("household", "recognized_income"),
    "가구 월소득 중위소득 대비": ("household", "household_income"),
    "도시근로자 월평균소득 대비 가구소득": ("household", "household_income"),
    "가구 총재산": ("household_assets",),
    "가구 순자산": ("household_assets",),
    # 1인 가구면 가구 재산을 본인 재산으로 본다.
    "본인 총재산": ("household", "personal_assets", "household_assets"),
    "본인 순자산": ("household", "personal_assets", "household_assets"),
    "자동차가액": ("car",),
    "주거 형태": ("housing_type",),
    "본인 명의 주택 보유": ("home_ownership",),
    "세대원 전원 무주택": ("home_ownership",),
    "등록 장애인": ("disability",),
    "중증 장애인": ("disability",),
    "재학 여부": ("student",),
    "학교 구분": ("student",),
    "혼인 상태": ("marriage",),
    "혼인 기간": ("marriage",),
    "부부합산 연소득": ("income", "marriage"),
    "맞벌이": ("income", "marriage"),
    "자녀 수": ("children",),
    "막내 자녀 나이": ("children",),
    "6세 이하 자녀": ("children",),
    "임신 중": ("pregnancy",),
    "국적": ("nationality",),
    **{field: ("special_targets",) for field in base.SPECIAL_TARGETS},
    "기초생활보장 수급자": ("basic_benefit",),
    "기초생활보장 수급 가구": ("basic_benefit",),
    **{field: ("basic_benefit",) for field in base.BENEFIT_TYPES},
    "차상위계층": ("near_poverty",),
    "한부모가족": ("single_parent",),
    "구직 등록": ("job_seek",),
    "자립준비청년": ("protection",),
    "신용점수(KCB)": ("credit",),
    "신용점수(NICE)": ("credit",),
}
QUESTION_ORDER = list(QUESTIONS)


NOT_READY = "간편 정책 찾기에 필요한 자격 경로 데이터가 준비되지 않았어요. 잠시 후 다시 시도해주세요."
# 판정 엔진이 쓰는 것과 같은 시드 파일. 읽기만 한다.
SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "eligibility_paths.json"


@lru_cache(maxsize=4)
def _seed_shape(path: str, mtime_ns: int, size: int) -> dict[str, tuple[str, int, int, int]]:
    """시드의 정책별 (원문 해시, 경로 수(공통 포함), 비교 조건 수, 확인 사항 수). seed_from_file이 만드는 구조와 같다."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    shape = {}
    for item in data["policies"]:
        if item.get("status", "reviewed") != "reviewed":
            continue
        paths = item["paths"]
        shape[item["serv_id"]] = (
            item["source_sha256"], 1 + len(paths),
            len(item.get("common", [])) + sum(len(p.get("conditions", [])) for p in paths),
            len(item.get("common_checks", [])) + sum(len(p.get("checks", [])) for p in paths))
    return shape


def _seed() -> dict[str, tuple[str, int, int, int]] | None:
    try:
        stat = SEED_PATH.stat()  # 파일이 바뀌면 다시 읽는다.
        return _seed_shape(str(SEED_PATH), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError, KeyError, TypeError):
        return None  # 시드를 읽을 수 없으면 DB 구조 점검만 한다.


def _require_ready(db: Session) -> None:
    """경로 데이터가 판정에 쓸 만큼 적재됐는지 읽기 전용으로 확인한다. DB를 바꾸지 않는다.

    1) 경로 행이 하나도 없으면 멈춘다. 엔진 load()는 이때 시드를 자동 적재(쓰기)하므로 그 전에 막는다.
    2) 검수 기록마다 공통 경로(_common)가 정확히 하나 있어야 한다(seed_from_file이 항상 만든다).
    3) 시드에 있고 원문도 DB에 있는 정책은 검수 기록이 있어야 한다. 원문 해시가 시드와 같으면(같은 시드 버전)
       경로·비교 조건·확인 사항 수도 시드와 같아야 한다. 해시가 다르면 다른 버전 시드로 보고 수는 비교하지 않는다.
    """
    if not settings.use_eligibility_paths or settings.use_llm_judge:
        raise HTTPException(503, "간편 정책 찾기는 자격 경로 판정이 켜진 서버에서만 사용할 수 있어요.")
    records = {sid: (status, sha) for sid, status, sha in db.execute(
        select(PolicyEligibility.serv_id, PolicyEligibility.status, PolicyEligibility.source_sha256))}
    if not any(status == "reviewed" for status, _ in records.values()):
        raise HTTPException(503, NOT_READY)
    paths, commons, checks = Counter(), Counter(), Counter()
    for sid, key, path_checks in db.execute(
            select(EligibilityPath.serv_id, EligibilityPath.path_key, EligibilityPath.checks)):
        paths[sid] += 1
        commons[sid] += key == COMMON_PATH
        checks[sid] += len(path_checks or [])
    conditions = Counter(dict(db.execute(
        select(EligibilityPath.serv_id, func.count(EligibilityPathCondition.id))
        .join(EligibilityPathCondition, EligibilityPathCondition.path_id == EligibilityPath.id)
        .group_by(EligibilityPath.serv_id)).all()))
    if any(status == "reviewed" and commons[sid] != 1 for sid, (status, _) in records.items()):
        raise HTTPException(503, NOT_READY)
    seed = _seed()
    if seed is None:
        return
    services = set(db.scalars(select(WelfareService.serv_id)))
    for sid, (sha, path_count, condition_count, check_count) in seed.items():
        if sid not in services:
            continue
        status, stored_sha = records.get(sid, (None, None))
        if status != "reviewed":
            raise HTTPException(503, NOT_READY)
        if stored_sha == sha and (paths[sid], conditions[sid], checks[sid]) != (path_count, condition_count, check_count):
            raise HTTPException(503, NOT_READY)


def _label(category: str) -> str:
    if category not in CATEGORIES:
        raise HTTPException(422, "지원하지 않는 정책 분야예요.")
    return CATEGORIES[category][0]


def _services(db: Session, category: str) -> list[WelfareService]:
    return [s for s in db.query(WelfareService).order_by(WelfareService.serv_name).all()
            if category in categories_of(s.interest_categories)]


def _path_records(db: Session, ids: set[str]) -> dict[str, PolicyEligibility]:
    """판정 엔진(eligibility_path_service.load)과 같은 검수 상태 기준. 읽기 전용이라 시드 적재를 하지 않는다."""
    query = db.query(PolicyEligibility).options(
        selectinload(PolicyEligibility.paths).selectinload(EligibilityPath.conditions))
    return {r.serv_id: r for r in query.filter(PolicyEligibility.status == "reviewed",
                                               PolicyEligibility.serv_id.in_(ids))}


def categories(db: Session) -> QuickCategoriesResponse:
    _require_ready(db)
    counts = {key: 0 for key in CATEGORIES}
    for (interest,) in db.query(WelfareService.interest_categories):
        for key in categories_of(interest):
            counts[key] += 1
    return QuickCategoriesResponse(categories=[
        QuickCategory(id=key, label=label, policy_count=counts[key]) for key, (label, _) in CATEGORIES.items()])


def category_detail(db: Session, category: str) -> QuickCategoryDetail:
    _require_ready(db)
    return _detail(db, category)


def _detail(db: Session, category: str) -> QuickCategoryDetail:
    label = _label(category)
    services = _services(db, category)
    records = _path_records(db, {s.serv_id for s in services})
    field_policies: dict[str, set[str]] = {}
    checks = 0
    path_policies = 0
    for service in services:
        record = records.get(service.serv_id)
        # 원문이 바뀐 정책은 엔진도 경로를 쓰지 않으므로 질문 근거에서도 뺀다.
        if record is None or record.source_sha256 != base.source_hash(service):
            continue
        path_policies += 1
        for path in record.paths:
            checks += len(path.checks or [])
            for condition in path.conditions:
                field_policies.setdefault(condition.field, set()).add(service.serv_id)
    needed: dict[str, set[str]] = {"age": set()}
    fields, unsupported = [], []
    for field, ids in sorted(field_policies.items(), key=lambda item: (-len(item[1]), item[0])):
        questions = FIELD_QUESTIONS.get(field)
        if questions is None:
            unsupported.append(field)
            continue
        for question in questions:
            needed.setdefault(question, set()).update(ids)
        fields.append(QuickField(field=field, policy_count=len(ids), questions=list(questions)))
    ordered = [q for q in QUESTION_ORDER if q in needed]
    return QuickCategoryDetail(id=category, label=label, policy_count=len(services), path_policy_count=path_policies,
                               questions=ordered, question_policy_counts={q: len(needed[q]) for q in ordered},
                               fields=fields, unsupported_fields=unsupported, check_count=checks)


def _profile(answers: QuickAnswers) -> tuple[User, dict]:
    """기존 진단 화면(toProfile)과 같은 모양으로 만들되, 응답한 항목만 넣는다."""
    a = answers
    employment = a.employment
    # 기존 진단 요청과 같게 아르바이트는 고용 상태 OTHER + 세부 PART_TIME으로 보낸다.
    user = User(age=a.age, region=a.region, income_level=a.income_monthly_won,
                employment_status="OTHER" if employment == "PART_TIME" else employment)
    top = {"gender": a.gender, "household_size": a.household_size, "housing_type": a.housing_type,
           "owns_home": None if a.owns_home is None else a.owns_home == "YES",
           "disability_status": a.disability_status, "student_status": a.student_status,
           "marital_status": a.marital_status, "children_count": a.children_count}
    extra = {
        "employment_detail": employment,
        "household_monthly_income_won": a.household_monthly_income_won,
        "household_income_recognition_known": "YES" if a.recognized_household_income_won is not None else None,
        "recognized_household_income_won": a.recognized_household_income_won,
        "asset_amount_won": a.asset_amount_won,
        "household_debt_won": a.household_debt_won,
        "personal_asset_amount_won": a.personal_asset_amount_won,
        "personal_debt_won": a.personal_debt_won,
        "car_value_won": a.car_value_won,
        "household_homeless": a.household_homeless,
        "severe_disability": a.severe_disability,
        "school_level": a.school_level,
        "marriage_years": a.marriage_years,
        "spouse_monthly_income_won": a.spouse_monthly_income_won,
        "youngest_child_age": a.youngest_child_age,
        "pregnancy": a.pregnancy,
        "nationality": a.nationality,
        "special_targets": a.special_targets,
        "basic_benefit_status": a.basic_benefit_status,
        "basic_benefit_types": a.basic_benefit_types,
        "household_basic_benefit_status": a.household_basic_benefit_status,
        "near_poverty_status": a.near_poverty_status,
        "single_parent_support_status": a.single_parent_support_status,
        "job_seek_registration": a.job_seek_registration,
        "child_welfare_protection_experience": a.child_welfare_protection_experience,
        "protection_ended": a.protection_ended,
        "credit_bureau": a.credit_bureau,
        "credit_score": a.credit_score,
    }
    profile = {key: value for key, value in top.items() if value is not None}
    profile["additional_conditions"] = {"profile_schema_version": 3,
                                        **{key: value for key, value in extra.items() if value is not None}}
    return user, profile


def _check_scope(detail: QuickCategoryDetail, answers: QuickAnswers) -> None:
    allowed = {key for question in detail.questions for key in QUESTIONS[question]}
    extra = sorted(key for key in answers.model_dump(exclude_none=True) if key not in allowed)
    if extra:
        raise HTTPException(422, "선택한 분야에서 비교하지 않는 항목이 포함되어 있어요. 분야를 다시 선택해주세요.")
    if answers.region is not None and EligibilityConditionService.canonical_sido_from_profile_region(answers.region) is None:
        raise HTTPException(422, "거주 지역을 목록에서 다시 선택해주세요.")


def evaluate(db: Session, category: str, answers: QuickAnswers) -> QuickEvaluateResponse:
    # 경로 행이 있음을 먼저 확인했으므로 아래 analyze_user 안의 load()는 시드를 적재하지 않는다.
    _require_ready(db)
    detail = _detail(db, category)
    _check_scope(detail, answers)
    user, profile = _profile(answers)
    try:
        result = EligibilityMatchingService().analyze_user(db, user, profile)
    finally:
        # 커밋하지 않은 변경이 남지 않게 한다(이미 커밋된 쓰기는 되돌리지 못하므로 위 점검으로 막는다).
        db.rollback()
    services = _services(db, category)
    ids = {s.serv_id for s in services}
    analyses = [a for a in result["analysis_results"] if a["policy_id"] in ids]
    summary = EligibilityMatchingService._summarize(services, analyses)
    urls = {a["policy_id"]: a["detail_url"] for a in analyses}
    for policy in summary["policies"]:
        policy["detail_url"] = urls.get(policy["policy_id"], "")
    return QuickEvaluateResponse(category=category, category_label=detail.label,
                                 evaluated_at=datetime.now(timezone.utc).isoformat(),
                                 matched=MatchedPoliciesResponse(**hide_input_values(summary)))
