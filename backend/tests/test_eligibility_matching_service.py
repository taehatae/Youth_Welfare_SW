import pytest

from app.models.user import User
from app.models.welfare_eligibility_condition import (
    WelfareEligibilityCondition,
)
from app.models.welfare_service import WelfareService
from app.services.eligibility_condition_service import (
    EligibilityConditionService,
)
from app.services.eligibility_matching_service import (
    EligibilityMatchingService,
)


def make_user(age: int) -> User:
    return User(
        age=age,
        region="서울특별시",
        income_level=0,
        employment_status="OTHER",
    )


def make_service() -> WelfareService:
    return WelfareService(
        serv_id="synthetic-service",
        serv_name="합성 테스트 서비스",
        detail_url="",
    )


def make_condition(
    *,
    operator: str,
    value_number: float | None,
    upper_value_number: float | None = None,
) -> WelfareEligibilityCondition:
    return WelfareEligibilityCondition(
        serv_id="synthetic-service",
        condition_type="age",
        operator=operator,
        value_text="합성 테스트 연령 조건",
        value_number=value_number,
        upper_value_number=upper_value_number,
        unit="세",
        source_field="selection_criteria",
        source_text="합성 테스트 연령 조건",
        comparison_ready=True,
        parse_status="parsed",
        confidence=1.0,
    )


def analyze(age: int, conditions: list[WelfareEligibilityCondition]) -> dict:
    return EligibilityMatchingService().analyze_service(
        user=make_user(age),
        service=make_service(),
        conditions=conditions,
    )


def make_profile_condition(
    *,
    condition_type: str,
    value_text: str,
    unit: str,
    source_text: str,
    comparison_ready: bool = True,
    parse_status: str = "parsed",
) -> WelfareEligibilityCondition:
    return WelfareEligibilityCondition(
        serv_id="synthetic-service",
        condition_type=condition_type,
        operator="equals",
        value_text=value_text,
        value_number=None,
        upper_value_number=None,
        unit=unit,
        source_field="selection_criteria",
        source_text=source_text,
        comparison_ready=comparison_ready,
        parse_status=parse_status,
        confidence=1.0 if comparison_ready else 0.0,
    )


@pytest.mark.parametrize(
    ("age", "expected_status", "expected_gap_count"),
    [
        (20, "eligible", 0),
        (24, "eligible", 0),
        (19, "ineligible", 1),
        (25, "ineligible", 1),
    ],
)
def test_between_includes_endpoints_and_rejects_adjacent_ages(
    age,
    expected_status,
    expected_gap_count,
):
    result = analyze(
        age,
        [make_condition(
            operator="between",
            value_number=20,
            upper_value_number=24,
        )],
    )

    assert result["status"] == expected_status
    assert len(result["gap_conditions"]) == expected_gap_count
    assert result["review_conditions"] == []


@pytest.mark.parametrize(
    ("operator", "age", "expected_status", "expected_gap_count"),
    [
        ("gte", 19, "ineligible", 1),
        ("gte", 20, "eligible", 0),
        ("gt", 20, "ineligible", 1),
        ("gt", 21, "eligible", 0),
        ("lte", 20, "eligible", 0),
        ("lte", 21, "ineligible", 1),
        ("lt", 19, "eligible", 0),
        ("lt", 20, "ineligible", 1),
    ],
)
def test_single_bound_operators_use_their_exact_boundary(
    operator,
    age,
    expected_status,
    expected_gap_count,
):
    result = analyze(
        age,
        [make_condition(operator=operator, value_number=20)],
    )

    assert result["status"] == expected_status
    assert len(result["gap_conditions"]) == expected_gap_count
    assert result["review_conditions"] == []


@pytest.mark.parametrize(
    ("operator", "value_number", "upper_value_number"),
    [
        ("gte", None, None),
        ("between", 20, None),
        ("equals", 20, None),
    ],
)
def test_missing_numbers_and_unsupported_operators_need_review(
    operator,
    value_number,
    upper_value_number,
):
    result = analyze(
        21,
        [make_condition(
            operator=operator,
            value_number=value_number,
            upper_value_number=upper_value_number,
        )],
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 1


def test_unrecognized_condition_in_same_sentence_is_not_ignored():
    source = "만 20세 이상이며 가구원 3인 이상"
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    assert [condition["condition_type"] for condition in parsed] == [
        "age",
        "other",
    ]
    assert parsed[0]["value_text"] == "만 20세 이상"
    assert parsed[0]["source_text"] == source
    assert parsed[0]["source_field"] == "selection_criteria"
    assert parsed[0]["parse_status"] == "parsed"
    assert parsed[0]["comparison_ready"] is True
    assert parsed[1]["value_text"] == "가구원 3인 이상"
    assert parsed[1]["source_text"] == source
    assert parsed[1]["source_field"] == "selection_criteria"
    assert parsed[1]["parse_status"] == "manual_review"
    assert parsed[1]["comparison_ready"] is False

    conditions = [
        WelfareEligibilityCondition(
            serv_id="synthetic-service",
            **item,
        )
        for item in parsed
    ]

    result = analyze(21, conditions)

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert any(
        "가구원 3인 이상" in condition["required_value"]
        for condition in result["review_conditions"]
    )


def test_recognized_age_and_target_group_do_not_add_duplicate_other():
    source = "만 20세 이상이며 장애인"

    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="target_details",
    )

    assert [condition["condition_type"] for condition in parsed] == [
        "age",
        "target_group",
    ]
    assert all(condition["source_text"] == source for condition in parsed)
    assert all(condition["source_field"] == "target_details" for condition in parsed)


def test_age_only_sentence_keeps_existing_parsed_condition_without_other():
    source = "만 20세 이상"

    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    assert len(parsed) == 1
    assert parsed[0]["condition_type"] == "age"
    assert parsed[0]["value_text"] == source
    assert parsed[0]["source_text"] == source
    assert parsed[0]["source_field"] == "selection_criteria"
    assert parsed[0]["parse_status"] == "parsed"
    assert parsed[0]["comparison_ready"] is True


def test_age_range_keeps_between_values_without_duplicate_other():
    source = "만 19~34세"

    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="target_details",
    )

    assert len(parsed) == 1
    assert parsed[0]["condition_type"] == "age"
    assert parsed[0]["operator"] == "between"
    assert parsed[0]["value_number"] == 19.0
    assert parsed[0]["upper_value_number"] == 34.0
    assert parsed[0]["value_text"] == source
    assert parsed[0]["source_text"] == source
    assert parsed[0]["source_field"] == "target_details"
    assert parsed[0]["parse_status"] == "parsed"
    assert parsed[0]["comparison_ready"] is True


def test_or_age_alternatives_are_sent_to_manual_review():
    source = "만 19~24세 또는 만 25~34세"
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    conditions = [
        WelfareEligibilityCondition(
            serv_id="synthetic-service",
            **item,
        )
        for item in parsed
    ]

    result = analyze(27, conditions)

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 2
    assert all(
        condition["condition_type"] == "age"
        and condition["status"] == "needs_review"
        for condition in result["review_conditions"]
    )


@pytest.mark.parametrize(
    "source",
    [
        "만 19~24세 아니면 만 25~34세",
        "만 19~24세\n또는 만 25~34세",
        "만 19~24세. 또는 만 25~34세",
    ],
    ids=["unsupported-or-word", "newline-split", "sentence-split"],
)
def test_split_or_age_alternatives_are_not_marked_ineligible(source):
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    age_conditions = [
        item for item in parsed if item["condition_type"] == "age"
    ]
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
    ]

    result = analyze(27, conditions)

    assert len(age_conditions) == 2
    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert sum(
        item["condition_type"] == "age"
        for item in result["review_conditions"]
    ) == 2


def test_separate_age_fragments_without_known_relation_need_review():
    parsed = EligibilityConditionService.parse_text(
        "만 19~24세\n만 25~34세",
        source_field="selection_criteria",
    )
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
    ]

    result = analyze(27, conditions)

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 2


def test_unrelated_or_connector_keeps_age_comparison_under_policy_b():
    source = "만 20세 이상이며 신청 방법은 방문 또는 온라인"
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    conditions = [
        WelfareEligibilityCondition(
            serv_id="synthetic-service",
            **item,
        )
        for item in parsed
    ]

    result = analyze(19, conditions)

    assert result["status"] == "needs_review"
    assert len(result["gap_conditions"]) == 1
    assert result["gap_conditions"][0]["condition_type"] == "age"
    assert len(result["review_conditions"]) == 1
    assert result["review_conditions"][0]["condition_type"] == "other"


def test_api_excerpt_income_ratio_upper_bound_is_preserved_as_residual():
    # 실제 API 발췌: WLF00000026 선정 기준에서 확인한 문구.
    source = "기준중위소득 50% 초과 100% 이하"

    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    income_conditions = [
        item for item in parsed if item["condition_type"] == "income_ratio"
    ]
    residual_conditions = [
        item for item in parsed if item["condition_type"] == "other"
    ]

    assert [(item["operator"], item["value_number"]) for item in income_conditions] == [
        ("gt", 50.0),
        ("lte", 100.0),
    ]
    assert all(item["comparison_ready"] is False for item in income_conditions)
    assert all(item["unit"] == "%" for item in income_conditions)
    assert all(item["source_text"] == source for item in income_conditions)
    assert residual_conditions == []


def test_api_excerpt_income_ratio_with_postposition_is_preserved_for_review():
    # 실제 API 발췌: WLF00001138 선정 기준에서 확인한 문구.
    source = "소득인정액이 기준 중위소득의 40%를 초과한 자"

    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    income_conditions = [
        item for item in parsed if item["condition_type"] == "income_ratio"
    ]
    assert len(income_conditions) == 1
    assert income_conditions[0]["operator"] == "gt"
    assert income_conditions[0]["value_number"] == 40.0
    assert income_conditions[0]["unit"] == "income_recognition"
    assert income_conditions[0]["source_text"] == source
    assert income_conditions[0]["source_field"] == "selection_criteria"
    assert income_conditions[0]["parse_status"] == "parsed"
    assert income_conditions[0]["comparison_ready"] is True


@pytest.mark.parametrize("source", ["만 18세 이후", "만 15세 이후"])
def test_api_excerpt_age_after_phrases_are_not_assumed_comparable(source):
    # 실제 API 발췌: WLF00001175. '이후'를 이상과 같다고 추정하지 않는다.
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    assert not any(item["condition_type"] == "age" for item in parsed)
    assert any(
        item["condition_type"] == "other"
        and source in item["value_text"]
        and item["parse_status"] == "manual_review"
        and item["comparison_ready"] is False
        for item in parsed
    )


@pytest.mark.parametrize(
    "source",
    [
        "4인 가구 기준",
        "특례수급가구의 근로 능력이 있는 가구원",
    ],
)
def test_api_excerpt_household_phrases_are_preserved_for_review(source):
    # 실제 API 발췌: 각각 WLF00000026, WLF00001138.
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    assert parsed
    assert any(
        item["condition_type"] in {"other", "target_group", "employment"}
        and item["source_text"] == source
        and item["source_field"] == "selection_criteria"
        and item["comparison_ready"] is False
        for item in parsed
    )
    assert not any(item["comparison_ready"] for item in parsed)


@pytest.mark.parametrize(
    "source",
    [
        "지역 및 개인 여건",
        "시/군/구청장의 결정에 따라 참여 가능",
    ],
)
def test_api_excerpt_local_discretion_phrases_are_not_auto_comparable(source):
    # 실제 API 발췌: WLF00001138. 지역/재량 문구를 자격 자동 판정으로 보지 않는다.
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    assert parsed
    assert all(item["comparison_ready"] is False for item in parsed)
    assert any(
        item["condition_type"] in {"other", "region"}
        and item["parse_status"] == "manual_review"
        for item in parsed
    )


@pytest.mark.parametrize(
    "source",
    [
        "다음 사항 중 어느 하나",
        "다만 특별한 사유로 아동복지심의위원회에서 심의·의결한 경우",
        "단 정신질환 등 별도 판단이 필요한 경우",
    ],
)
def test_api_excerpt_alternatives_and_exceptions_remain_unstructured_review(source):
    # 앞의 두 문구는 WLF00001175 실제 발췌이며, 마지막은 합성 사례다.
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    assert parsed
    assert all(item["comparison_ready"] is False for item in parsed)
    assert any(
        item["condition_type"] in {"other", "target_group", "external_review"}
        and item["parse_status"] == "manual_review"
        and source in item["source_text"]
        for item in parsed
    )


def test_or_alternative_using_anileum_is_sent_to_review():
    # 합성 문구: 실제 서비스 원문이라고 주장하지 않는다.
    source = "만 19~24세 아니면 만 25~34세"
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
    ]

    result = analyze(27, conditions)

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert sum(
        item["condition_type"] == "age"
        for item in result["review_conditions"]
    ) == 2


@pytest.mark.parametrize(
    "condition_type",
    ["income_ratio", "other", "region"],
)
def test_non_comparable_income_household_and_region_conditions_need_review(
    condition_type,
):
    # 합성 모델 조건: 사용자에게 그럴듯한 값이 있어도 자동 비교 대상이 아니다.
    condition = WelfareEligibilityCondition(
        serv_id="synthetic-service",
        condition_type=condition_type,
        operator="lte" if condition_type == "income_ratio" else "contains",
        value_text="합성 수동 검토 조건",
        value_number=10.0 if condition_type == "income_ratio" else None,
        upper_value_number=None,
        unit="%" if condition_type == "income_ratio" else "",
        source_field="selection_criteria",
        source_text="합성 수동 검토 조건",
        comparison_ready=False,
        parse_status="manual_review",
        confidence=0.0,
    )

    result = analyze(20, [condition])

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 1


def test_age_passes_but_non_comparable_condition_keeps_service_under_review():
    result = analyze(
        20,
        [
            make_condition(operator="gte", value_number=20),
            WelfareEligibilityCondition(
                serv_id="synthetic-service",
                condition_type="other",
                operator="unknown",
                value_text="합성 가구 조건",
                value_number=None,
                upper_value_number=None,
                unit="",
                source_field="selection_criteria",
                source_text="합성 연령 및 가구 조건",
                comparison_ready=False,
                parse_status="manual_review",
                confidence=0.0,
            ),
        ],
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 1


def test_gap_and_review_return_needs_review_without_moving_conditions():
    result = analyze(
        19,
        [
            make_condition(operator="gte", value_number=20),
            WelfareEligibilityCondition(
                serv_id="synthetic-service",
                condition_type="other",
                operator="unknown",
                value_text="관계가 불명확한 합성 조건",
                value_number=None,
                upper_value_number=None,
                unit="",
                source_field="selection_criteria",
                source_text="연령과 관계를 확정할 수 없는 합성 문구",
                comparison_ready=False,
                parse_status="manual_review",
                confidence=0.0,
            ),
        ],
    )

    assert result["status"] == "needs_review"
    assert len(result["gap_conditions"]) == 1
    assert len(result["review_conditions"]) == 1
    assert result["gap_conditions"][0]["status"] == "failed"
    assert result["review_conditions"][0]["status"] == "needs_review"


def test_ambiguous_age_failure_with_review_does_not_confirm_ineligibility():
    # 합성 문구: OR/예외 관계를 완전히 해석했다고 가정하지 않는다.
    parsed = EligibilityConditionService.parse_text(
        "만 20세 이상 또는 별도 심사 대상",
        source_field="selection_criteria",
    )
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
    ]

    result = analyze(19, conditions)

    assert any(item["condition_type"] == "age" for item in parsed)
    assert any(item["condition_type"] == "other" for item in parsed)
    assert result["status"] == "needs_review"
    assert len(result["gap_conditions"]) == 1
    assert result["review_conditions"]


def test_gap_without_review_returns_ineligible():
    result = analyze(
        19,
        [make_condition(operator="gte", value_number=20)],
    )

    assert result["status"] == "ineligible"
    assert len(result["gap_conditions"]) == 1
    assert result["review_conditions"] == []


def test_analyze_user_includes_only_eligible_services_in_policies():
    eligible_service = make_service()
    eligible_service.serv_id = "eligible-service"
    eligible_service.serv_name = "충족 서비스"
    ineligible_service = WelfareService(
        serv_id="ineligible-service",
        serv_name="미충족 서비스",
        detail_url="",
    )
    review_service = WelfareService(
        serv_id="review-service",
        serv_name="검토 서비스",
        detail_url="",
    )
    conditions = [
        WelfareEligibilityCondition(
            serv_id="eligible-service",
            condition_type="age",
            operator="gte",
            value_text="만 20세 이상",
            value_number=20.0,
            upper_value_number=None,
            unit="세",
            source_field="selection_criteria",
            source_text="만 20세 이상",
            comparison_ready=True,
            parse_status="parsed",
            confidence=1.0,
        ),
        WelfareEligibilityCondition(
            serv_id="ineligible-service",
            condition_type="age",
            operator="gte",
            value_text="만 30세 이상",
            value_number=30.0,
            upper_value_number=None,
            unit="세",
            source_field="selection_criteria",
            source_text="만 30세 이상",
            comparison_ready=True,
            parse_status="parsed",
            confidence=1.0,
        ),
        WelfareEligibilityCondition(
            serv_id="review-service",
            condition_type="other",
            operator="unknown",
            value_text="검토 조건",
            value_number=None,
            upper_value_number=None,
            unit="",
            source_field="selection_criteria",
            source_text="검토 조건",
            comparison_ready=False,
            parse_status="manual_review",
            confidence=0.0,
        ),
    ]

    class Query:
        def __init__(self, model):
            self.model = model

        def order_by(self, *_args):
            return self

        def all(self):
            if self.model is WelfareService:
                return [eligible_service, ineligible_service, review_service]
            return conditions

    class Session:
        def query(self, model):
            return Query(model)

    result = EligibilityMatchingService().analyze_user(
        db=Session(),
        user=make_user(20),
    )

    assert [policy["policy_id"] for policy in result["policies"]] == [
        "eligible-service"
    ]
    statuses = {
        item["policy_id"]: item["status"]
        for item in result["analysis_results"]
    }
    assert statuses == {
        "eligible-service": "eligible",
        "ineligible-service": "ineligible",
        "review-service": "needs_review",
    }


def test_recommendation_marks_all_confirmed_conditions_as_priority():
    result = analyze(
        20,
        [make_condition(operator="gte", value_number=20)],
    )

    assert result["status"] == "eligible"
    assert result["recommendation_status"] == "priority_recommendation"
    assert result["recommendation_reason"]
    assert result["recommendation_uncertainty"] is None
    assert [item["condition_type"] for item in result["confirmed_conditions"]] == [
        "age"
    ]
    assert result["gap_conditions"] == []
    assert result["review_conditions"] == []
    assert result["match_score"] == 100.0


def test_recommendation_marks_passed_conditions_with_reviews_as_consideration():
    review_condition = make_profile_condition(
        condition_type="other",
        value_text="수급 자격 확인",
        unit="",
        source_text="수급 자격 확인",
        comparison_ready=False,
        parse_status="manual_review",
    )
    result = analyze(
        20,
        [make_condition(operator="gte", value_number=20), review_condition],
    )

    assert result["status"] == "needs_review"
    assert result["recommendation_status"] == "priority_consideration"
    assert "핵심" in result["recommendation_uncertainty"]
    assert [item["condition_type"] for item in result["confirmed_conditions"]] == [
        "age"
    ]
    assert result["gap_conditions"] == []
    assert [item["condition_type"] for item in result["review_conditions"]] == [
        "other"
    ]
    assert result["match_score"] == 100.0


def test_recommendation_marks_clear_selection_criteria_gap_as_mismatch():
    result = analyze(
        19,
        [make_condition(operator="gte", value_number=20)],
    )

    assert result["status"] == "ineligible"
    assert result["recommendation_status"] == "condition_mismatch"
    assert result["confirmed_conditions"] == []
    assert len(result["gap_conditions"]) == 1
    assert result["review_conditions"] == []


def test_recommendation_keeps_gap_and_review_as_additional_review():
    review_condition = make_profile_condition(
        condition_type="other",
        value_text="수급 자격 확인",
        unit="",
        source_text="수급 자격 확인",
        comparison_ready=False,
        parse_status="manual_review",
    )
    result = analyze(
        19,
        [make_condition(operator="gte", value_number=20), review_condition],
    )

    assert result["status"] == "needs_review"
    assert result["recommendation_status"] == "additional_review"
    assert result["recommendation_uncertainty"]
    assert result["confirmed_conditions"] == []
    assert len(result["gap_conditions"]) == 1
    assert len(result["review_conditions"]) == 1
    assert result["match_score"] == 0.0


@pytest.mark.parametrize(
    "source_text",
    [
        "만 19~24세 또는 만 25~34세",
        "만 19~24세, 다만 예외 참여 가능",
    ],
)
def test_recommendation_does_not_confirm_ambiguous_gap_as_mismatch(source_text):
    condition = make_condition(operator="gte", value_number=20)
    condition.source_text = source_text
    result = analyze(19, [condition])

    assert result["status"] == "ineligible"
    assert result["recommendation_status"] == "additional_review"
    assert result["recommendation_uncertainty"]
    assert len(result["gap_conditions"]) == 1


def test_recommendation_does_not_confirm_gap_from_non_selection_source():
    condition = make_condition(operator="gte", value_number=20)
    condition.source_field = "target_details"
    result = analyze(19, [condition])

    assert result["status"] == "ineligible"
    assert result["recommendation_status"] == "additional_review"
    assert result["recommendation_uncertainty"]


def test_recommendation_for_no_comparable_conditions_requires_review():
    condition = make_profile_condition(
        condition_type="other",
        value_text="정책 원문 검토",
        unit="",
        source_text="정책 원문 검토",
        comparison_ready=False,
        parse_status="manual_review",
    )
    result = analyze(20, [condition])

    assert result["status"] == "needs_review"
    assert result["recommendation_status"] == "additional_review"
    assert result["confirmed_conditions"] == []


def test_recommendation_for_missing_conditions_requires_review():
    result = analyze(20, [])

    assert result["status"] == "needs_review"
    assert result["recommendation_status"] == "additional_review"
    assert result["confirmed_conditions"] == []


def test_analyze_user_derives_recommendation_from_all_analysis_results():
    eligible_service = make_service()
    eligible_service.serv_id = "eligible-service"
    ineligible_service = WelfareService(
        serv_id="ineligible-service",
        serv_name="불일치 서비스",
        detail_url="",
    )
    review_service = WelfareService(
        serv_id="review-service",
        serv_name="검토 서비스",
        detail_url="",
    )
    conditions = [
        make_condition(operator="gte", value_number=20),
        WelfareEligibilityCondition(
            serv_id="ineligible-service",
            condition_type="age",
            operator="gte",
            value_text="연령 조건",
            value_number=30,
            upper_value_number=None,
            unit="age",
            source_field="selection_criteria",
            source_text="연령 조건",
            comparison_ready=True,
            parse_status="parsed",
            confidence=1.0,
        ),
        WelfareEligibilityCondition(
            serv_id="review-service",
            condition_type="other",
            operator="unknown",
            value_text="정책 원문 검토",
            value_number=None,
            upper_value_number=None,
            unit="",
            source_field="selection_criteria",
            source_text="정책 원문 검토",
            comparison_ready=False,
            parse_status="manual_review",
            confidence=0.0,
        ),
    ]
    conditions[0].serv_id = "eligible-service"

    class Query:
        def __init__(self, model):
            self.model = model

        def order_by(self, *_args):
            return self

        def all(self):
            if self.model is WelfareService:
                return [eligible_service, ineligible_service, review_service]
            return conditions

    class Session:
        def query(self, model):
            return Query(model)

    result = EligibilityMatchingService().analyze_user(
        db=Session(),
        user=make_user(20),
    )

    assert [item["policy_id"] for item in result["policies"]] == [
        "eligible-service"
    ]
    classifications = {
        item["policy_id"]: item["recommendation_status"]
        for item in result["analysis_results"]
    }
    assert classifications == {
        "eligible-service": "priority_recommendation",
        "ineligible-service": "condition_mismatch",
        "review-service": "additional_review",
    }


@pytest.mark.parametrize(
    ("age", "expected_status", "expected_gap_count"),
    [
        (20, "eligible", 0),
        (31, "ineligible", 1),
    ],
)
def test_explicit_and_age_requirements_are_compared_independently(
    age,
    expected_status,
    expected_gap_count,
):
    # 합성 문구: 두 연령 조건을 모두 충족해야 하는 명시적 AND 사례.
    parsed = EligibilityConditionService.parse_text(
        "만 19세 이상이며 만 30세 이하",
        source_field="selection_criteria",
    )
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
    ]

    result = analyze(age, conditions)

    assert [item["operator"] for item in parsed] == ["gte", "lte"]
    assert result["status"] == expected_status
    assert len(result["gap_conditions"]) == expected_gap_count
    assert result["review_conditions"] == []


def test_different_target_groups_and_age_ranges_are_not_merged():
    # 합성 문구: 한 서비스 원문에 서로 다른 대상 집단이 기재된 상황.
    source = (
        "기초생활수급자는 만 19~24세. "
        "차상위계층은 만 25~34세"
    )
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    age_conditions = [
        item for item in parsed if item["condition_type"] == "age"
    ]
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
    ]

    result = analyze(27, conditions)

    assert len(age_conditions) == 2
    assert age_conditions[0]["source_text"] != age_conditions[1]["source_text"]
    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert sum(
        item["condition_type"] == "age"
        for item in result["review_conditions"]
    ) == 2


def test_discretionary_age_condition_is_review_not_a_required_age_gap():
    # 합성 예외 사례: 연령 문구 뒤에 기관 판단에 따른 참여 가능 조건이 있다.
    parsed = EligibilityConditionService.parse_text(
        "만 65세 이상인 경우 지자체 판단에 따라 참여 가능",
        source_field="selection_criteria",
    )
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
    ]

    result = analyze(60, conditions)

    assert any(item["condition_type"] == "age" for item in parsed)
    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert any(
        item["condition_type"] == "age"
        for item in result["review_conditions"]
    )


def test_exception_text_on_separate_sentence_is_preserved_for_review():
    # 합성 예외 사례: 문장 분리 후에도 별도 심사 문구를 잃지 않는다.
    source = "만 20세 이상. 다만 정신질환 등 건강 상태에 따라 별도 심사"
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    exception_conditions = [
        item
        for item in parsed
        if item["condition_type"] == "other"
        and "다만 정신질환" in item["value_text"]
    ]
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
    ]

    result = analyze(19, conditions)

    assert len(exception_conditions) == 1
    assert exception_conditions[0]["parse_status"] == "manual_review"
    assert exception_conditions[0]["comparison_ready"] is False
    assert result["status"] == "needs_review"
    assert len(result["gap_conditions"]) == 1
    assert any(
        "다만 정신질환" in item["required_value"]
        for item in result["review_conditions"]
    )


def test_review_conditions_display_relevant_saved_profile_values():
    conditions = [
        WelfareEligibilityCondition(
            serv_id="synthetic-service",
            condition_type=condition_type,
            operator="contains",
            value_text=value_text,
            value_number=None,
            upper_value_number=None,
            unit="",
            source_field="selection_criteria",
            source_text=value_text,
            comparison_ready=False,
            parse_status="manual_review",
            confidence=0.0,
        )
        for condition_type, value_text in [
            ("region", "거주 지역 조건"),
            ("employment", "취업 상태 조건"),
            ("income_amount", "월 소득 기준"),
            ("income_ratio", "기준 중위소득 비율 기준"),
            ("other", "가구원 수 조건"),
            ("other", "주택 보유 조건"),
            ("other", "장애 여부 조건"),
            ("other", "자격 목록 조건"),
        ]
    ]
    user = make_user(25)
    user.income_level = 2_000_000
    result = EligibilityMatchingService().analyze_service(
        user=user,
        service=make_service(),
        conditions=conditions,
        eligibility_conditions={
            "household_size": 0,
            "owns_home": False,
            "disability_status": "YES",
            "qualifications": [],
            "additional_conditions": {"employment_detail": "PART_TIME"},
        },
    )

    current_values = [
        condition["current_value"]
        for condition in result["review_conditions"]
    ]
    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert result["match_score"] == 0.0
    assert current_values == [
        "서울특별시",
        "시간제 근로",
        "본인 월 소득 2,000,000원",
        "추가 정보 또는 비교 규칙 필요",
        "0명",
        "아니요",
        "예",
        "[]",
    ]


@pytest.mark.parametrize(
    ("profile_value", "expected_current_value"),
    [
        (None, "미입력"),
        ("", "미입력"),
        ("  ", "미입력"),
        ("UNKNOWN", "모름·확인 필요"),
        ("unknown", "모름·확인 필요"),
    ],
)
def test_unknown_or_empty_saved_profile_values_are_not_presented_as_confirmed(
    profile_value,
    expected_current_value,
):
    condition = WelfareEligibilityCondition(
        serv_id="synthetic-service",
        condition_type="other",
        operator="unknown",
        value_text="장애 여부 조건",
        value_number=None,
        upper_value_number=None,
        unit="",
        source_field="selection_criteria",
        source_text="장애 여부 조건",
        comparison_ready=False,
        parse_status="manual_review",
        confidence=0.0,
    )
    result = EligibilityMatchingService().analyze_service(
        user=make_user(25),
        service=make_service(),
        conditions=[condition],
        eligibility_conditions={"disability_status": profile_value},
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert (
        result["review_conditions"][0]["current_value"]
        == expected_current_value
    )


@pytest.mark.parametrize(
    ("source", "normalized"),
    [
        ("미취업자", "UNEMPLOYED"),
        ("중소기업 재직자", "EMPLOYED_SME"),
    ],
)
def test_explicit_single_employment_requirement_is_normalized(source, normalized):
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    employment = [item for item in parsed if item["condition_type"] == "employment"]
    assert len(employment) == 1
    assert employment[0]["value_text"] == normalized
    assert employment[0]["unit"] == "employment_status"
    assert employment[0]["operator"] == "equals"
    assert employment[0]["comparison_ready"] is True
    assert employment[0]["parse_status"] == "parsed"
    assert employment[0]["source_text"] == source
    assert not any(item["condition_type"] == "other" for item in parsed)


@pytest.mark.parametrize(
    "source",
    [
        "취업자",
        "근로자",
        "재직자",
        "미취업자가 아닌 청년",
        "미취업자 또는 중소기업 재직자",
        "중소기업 재직 후 3개월 이상",
    ],
)
def test_ambiguous_employment_text_is_not_marked_comparable(source):
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    employment = [item for item in parsed if item["condition_type"] == "employment"]
    assert not any(item["comparison_ready"] for item in employment)
    assert not any(item["parse_status"] == "parsed" for item in employment)


@pytest.mark.parametrize(
    ("source", "normalized", "comparison_ready"),
    [
        ("서울특별시 거주자", "서울특별시", True),
        ("주민등록상 서울특별시 거주자", "주민등록상 서울특별시 거주자", False),
        ("서울시에 주민등록을 둔 청년", "서울시에 주민등록을 둔 청년", False),
        ("서울시 거주자", "서울특별시", True),
    ],
)
def test_explicit_single_sido_residency_normalization_respects_verifiability(
    source,
    normalized,
    comparison_ready,
):
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    regions = [item for item in parsed if item["condition_type"] == "region"]
    assert len(regions) == 1
    assert regions[0]["value_text"] == normalized
    assert regions[0]["operator"] == ("equals" if comparison_ready else "contains")
    assert regions[0]["unit"] == ("sido" if comparison_ready else "")
    assert regions[0]["comparison_ready"] is comparison_ready
    assert regions[0]["parse_status"] == (
        "parsed" if comparison_ready else "manual_review"
    )
    assert regions[0]["source_text"] == source
    if comparison_ready:
        assert not any(item["condition_type"] == "other" for item in parsed)


@pytest.mark.parametrize(
    "source",
    [
        "주민등록상 서울특별시 거주자",
        "서울특별시에서 3년 이상 거주한 청년",
    ],
)
def test_residency_proof_or_duration_cannot_be_verified_by_region_string(source):
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
    ]

    user = make_user(25)
    user.region = "서울특별시 관악구"
    result = EligibilityMatchingService().analyze_service(
        user=user,
        service=make_service(),
        conditions=conditions,
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert result["review_conditions"]
    assert result["evaluated_conditions"] == 0


def test_legacy_unnormalized_region_value_text_is_not_reinterpreted_as_normalized():
    user = make_user(25)
    user.region = "서울특별시 관악구"
    # Legacy row shape: value_text kept the source phrase instead of the new
    # canonical SIDO value, even though its metadata claims it is comparable.
    condition = make_profile_condition(
        condition_type="region",
        value_text="서울특별시 거주자",
        unit="sido",
        source_text="서울특별시 거주자",
    )

    result = EligibilityMatchingService().analyze_service(
        user=user,
        service=make_service(),
        conditions=[condition],
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 1
    assert result["evaluated_conditions"] == 0
    assert result["match_score"] == 0.0


@pytest.mark.parametrize(
    "source",
    [
        "서울특별시 또는 경기도 거주자",
        "서울특별시에서 3년 이상 거주한 청년",
        "서울특별시 거주자가 아닌 경우",
        "서울특별시 거주 여부는 심사 후 결정",
    ],
)
def test_complex_or_qualified_region_text_remains_manual_review(source):
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    region = [item for item in parsed if item["condition_type"] == "region"]
    assert region
    assert not any(item["comparison_ready"] for item in region)
    assert all(item["parse_status"] == "manual_review" for item in region)


def test_split_profile_alternatives_and_multiple_profile_requirements_stay_manual():
    sources = [
        "서울시 거주자\n또는 경기도 거주자",
        "서울시 거주자\n중소기업 재직자",
        "미취업자\n중소기업 재직자",
    ]

    for source in sources:
        parsed = EligibilityConditionService.parse_text(
            source,
            source_field="selection_criteria",
        )
        profile_conditions = [
            item for item in parsed
            if item["condition_type"] in {"region", "employment"}
        ]
        assert profile_conditions
        assert not any(item["comparison_ready"] for item in profile_conditions)
        assert all(
            item["parse_status"] == "manual_review"
            for item in profile_conditions
        )


@pytest.mark.parametrize(
    ("required", "profile_status", "expected_status", "expected_score"),
    [
        ("UNEMPLOYED", "UNEMPLOYED", "eligible", 100.0),
        ("UNEMPLOYED", "EMPLOYED", "ineligible", 0.0),
        ("EMPLOYED_SME", "EMPLOYED_SME", "eligible", 100.0),
        ("EMPLOYED_SME", "EMPLOYED", "ineligible", 0.0),
        ("UNEMPLOYED", "OTHER", "needs_review", 0.0),
        ("UNEMPLOYED", "STUDENT", "needs_review", 0.0),
    ],
)
def test_explicit_employment_requirement_matches_only_trusted_enum(
    required,
    profile_status,
    expected_status,
    expected_score,
):
    user = make_user(25)
    user.employment_status = profile_status
    source_text = {
        "UNEMPLOYED": "미취업자",
        "EMPLOYED_SME": "중소기업 재직자",
    }[required]
    condition = make_profile_condition(
        condition_type="employment",
        value_text=required,
        unit="employment_status",
        source_text=source_text,
    )

    result = EligibilityMatchingService().analyze_service(
        user=user,
        service=make_service(),
        conditions=[condition],
    )

    assert result["status"] == expected_status
    assert result["match_score"] == expected_score
    assert len(result["gap_conditions"]) == int(expected_status == "ineligible")
    assert len(result["review_conditions"]) == int(expected_status == "needs_review")


def test_unvalidated_employment_detail_does_not_override_other_status():
    user = make_user(25)
    user.employment_status = "OTHER"
    condition = make_profile_condition(
        condition_type="employment",
        value_text="EMPLOYED_SME",
        unit="employment_status",
        source_text="중소기업 재직자",
    )

    result = EligibilityMatchingService().analyze_service(
        user=user,
        service=make_service(),
        conditions=[condition],
        eligibility_conditions={
            "additional_conditions": {"employment_detail": "EMPLOYED_SME"}
        },
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 1


@pytest.mark.parametrize(
    ("user_region", "expected_status"),
    [
        ("서울특별시 관악구", "eligible"),
        ("서울시 관악구", "eligible"),
        ("경기도 수원시", "ineligible"),
        ("관악구 서울특별시", "needs_review"),
        ("서울특별시관악구", "needs_review"),
        ("서울특별시청 관악구", "needs_review"),
        ("UNKNOWN", "needs_review"),
        ("", "needs_review"),
    ],
)
def test_single_sido_condition_uses_exact_region_prefix(user_region, expected_status):
    user = make_user(25)
    user.region = user_region
    condition = make_profile_condition(
        condition_type="region",
        value_text="서울특별시",
        unit="sido",
        source_text="서울특별시 거주자",
    )

    result = EligibilityMatchingService().analyze_service(
        user=user,
        service=make_service(),
        conditions=[condition],
    )

    assert result["status"] == expected_status
    assert len(result["gap_conditions"]) == int(expected_status == "ineligible")
    assert len(result["review_conditions"]) == int(expected_status == "needs_review")


def test_new_region_comparison_is_included_in_existing_score_and_policy_b():
    user = make_user(19)
    user.region = "서울특별시 관악구"
    age = make_condition(operator="gte", value_number=20)
    region = make_profile_condition(
        condition_type="region",
        value_text="서울특별시",
        unit="sido",
        source_text="서울특별시 거주자",
    )

    result = EligibilityMatchingService().analyze_service(
        user=user,
        service=make_service(),
        conditions=[age, region],
    )

    assert result["evaluated_conditions"] == 2
    assert result["passed_conditions"] == 1
    assert result["match_score"] == 50.0
    assert result["status"] == "ineligible"
    assert result["recommendation_status"] == "additional_review"
    assert result["recommendation_uncertainty"]
    assert [item["condition_type"] for item in result["gap_conditions"]] == ["age"]
    assert result["review_conditions"] == []


def test_auto_failure_and_ambiguous_profile_keep_policy_b_needs_review():
    user = make_user(19)
    user.region = "서울특별시 또는 경기도"
    age = make_condition(operator="gte", value_number=20)
    region = make_profile_condition(
        condition_type="region",
        value_text="서울특별시",
        unit="sido",
        source_text="서울특별시 거주자",
    )

    result = EligibilityMatchingService().analyze_service(
        user=user,
        service=make_service(),
        conditions=[age, region],
    )

    assert result["status"] == "needs_review"
    assert [item["condition_type"] for item in result["gap_conditions"]] == ["age"]
    assert [item["condition_type"] for item in result["review_conditions"]] == ["region"]
    assert result["match_score"] == 0.0


def test_review_condition_does_not_change_score_or_auto_result_of_evaluated_conditions():
    user = make_user(25)
    age = make_condition(operator="gte", value_number=20)
    review_condition = WelfareEligibilityCondition(
        serv_id="synthetic-service",
        condition_type="other",
        operator="unknown",
        value_text="합성 추가 확인 조건",
        value_number=None,
        upper_value_number=None,
        unit="",
        source_field="selection_criteria",
        source_text="합성 추가 확인 조건",
        comparison_ready=False,
        parse_status="manual_review",
        confidence=0.0,
    )

    result = EligibilityMatchingService().analyze_service(
        user=user,
        service=make_service(),
        conditions=[age, review_condition],
    )

    assert result["status"] == "needs_review"
    assert result["evaluated_conditions"] == 1
    assert result["passed_conditions"] == 1
    assert result["match_score"] == 100.0
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 1


@pytest.mark.parametrize(
    ("source", "field", "profile_value", "expected_status"),
    [
        ("기초생활수급자", "basic_benefit_status", "YES", "eligible"),
        ("기초생활수급자", "basic_benefit_status", "NO", "ineligible"),
        ("기초생활수급자", "basic_benefit_status", "UNKNOWN", "needs_review"),
        ("기초생활수급자", "basic_benefit_status", None, "needs_review"),
        ("차상위계층", "near_poverty_status", "YES", "eligible"),
        ("한부모가족 지원대상", "single_parent_support_status", "YES", "eligible"),
    ],
)
def test_exact_benefit_status_conditions_use_saved_self_report_conservatively(
    source,
    field,
    profile_value,
    expected_status,
):
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
    ]
    result = EligibilityMatchingService().analyze_service(
        user=make_user(25),
        service=make_service(),
        conditions=conditions,
        eligibility_conditions={
            "additional_conditions": {field: profile_value}
        },
    )

    assert len(conditions) == 1
    assert conditions[0].condition_type == "target_group"
    assert conditions[0].comparison_ready is True
    assert conditions[0].unit == field
    assert result["status"] == expected_status
    assert len(result["gap_conditions"]) == int(expected_status == "ineligible")
    assert len(result["review_conditions"]) == int(expected_status == "needs_review")


def test_exact_benefit_status_without_saved_value_stays_needs_review():
    parsed = EligibilityConditionService.parse_text(
        "차상위계층",
        source_field="selection_criteria",
    )
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
    ]

    result = EligibilityMatchingService().analyze_service(
        user=make_user(25),
        service=make_service(),
        conditions=conditions,
        eligibility_conditions={"additional_conditions": {}},
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 1


def test_household_income_is_not_used_as_personal_income_match():
    condition = WelfareEligibilityCondition(
        serv_id="synthetic-service",
        condition_type="income_amount",
        operator="lte",
        value_text="월 소득 2,000,000원 이하",
        value_number=2_000_000,
        upper_value_number=None,
        unit="원/월",
        source_field="selection_criteria",
        source_text="월 소득 2,000,000원 이하",
        comparison_ready=True,
        parse_status="parsed",
        confidence=0.9,
    )
    user = make_user(25)
    user.income_level = 3_000_000
    result = EligibilityMatchingService().analyze_service(
        user=user,
        service=make_service(),
        conditions=[condition],
        eligibility_conditions={
            "additional_conditions": {"household_monthly_income_won": 0}
        },
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert result["review_conditions"][0]["current_value"] == "본인 월 소득 3,000,000원"


@pytest.mark.parametrize(
    ("source", "operator", "percentage"),
    [
        ("소득인정액은 기준 중위소득 50% 이하", "lte", 50.0),
        ("소득인정액은 기준 중위소득 50% 미만", "lt", 50.0),
        ("소득인정액은 기준 중위소득 50% 이상", "gte", 50.0),
        ("소득인정액은 기준 중위소득 50% 초과", "gt", 50.0),
        ("소득인정액이 기준 중위소득의 40%를 초과", "gt", 40.0),
        ("소득인정액은 기준 중위소득 120% 이하", "lte", 120.0),
    ],
)
def test_explicit_recognized_income_ratio_is_parsed_for_comparison(
    source,
    operator,
    percentage,
):
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    ratio = [item for item in parsed if item["condition_type"] == "income_ratio"]

    assert len(ratio) == 1
    assert ratio[0]["operator"] == operator
    assert ratio[0]["value_number"] == percentage
    assert ratio[0]["unit"] == "income_recognition"
    assert ratio[0]["comparison_ready"] is True
    assert ratio[0]["parse_status"] == "parsed"


def test_median_income_interval_parses_both_bounds_without_losing_operator():
    source = "소득인정액은 기준 중위소득 50% 초과 100% 이하"
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    ratios = [item for item in parsed if item["condition_type"] == "income_ratio"]

    assert [(item["operator"], item["value_number"]) for item in ratios] == [
        ("gt", 50.0),
        ("lte", 100.0),
    ]
    assert all(item["comparison_ready"] for item in ratios)
    assert all(item["unit"] == "income_recognition" for item in ratios)


@pytest.mark.parametrize(
    "source",
    [
        "기준 중위소득 50% 이하",
        "가구 소득이 기준 중위소득 50% 이하",
        "소득인정액은 기준 중위소득 50% 이하 또는 80% 이하",
        "단, 소득인정액은 기준 중위소득 50% 이하",
    ],
)
def test_ambiguous_or_compound_median_income_conditions_remain_manual_review(source):
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    ratios = [item for item in parsed if item["condition_type"] == "income_ratio"]

    assert ratios
    assert all(item["comparison_ready"] is False for item in ratios)
    assert all(item["parse_status"] == "manual_review" for item in ratios)


def test_general_percentage_without_median_income_is_not_income_ratio():
    parsed = EligibilityConditionService.parse_text(
        "지원율 50% 이하",
        source_field="selection_criteria",
    )

    assert not any(item["condition_type"] == "income_ratio" for item in parsed)


def _median_income_analysis(
    *,
    amount,
    household_size=4,
    reference_year="2026",
    source="소득인정액은 기준 중위소득 50% 이하",
):
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **item)
        for item in parsed
        if item["condition_type"] == "income_ratio"
    ]
    service = make_service()
    service.reference_year = reference_year
    return EligibilityMatchingService().analyze_service(
        user=make_user(25),
        service=service,
        conditions=conditions,
        eligibility_conditions={
            "household_size": household_size,
            "additional_conditions": {
                "recognized_household_income_won": amount,
            },
        },
    )


@pytest.mark.parametrize(
    ("amount", "expected_status", "gap_count"),
    [
        (3_247_369, "eligible", 0),
        (3_247_368, "eligible", 0),
        (3_247_370, "ineligible", 1),
        (0, "eligible", 0),
    ],
)
def test_2026_four_person_median_income_50_percent_boundary(
    amount,
    expected_status,
    gap_count,
):
    result = _median_income_analysis(amount=amount)

    assert result["status"] == expected_status
    assert len(result["gap_conditions"]) == gap_count
    assert result["review_conditions"] == []
    assert result["match_score"] == (0.0 if gap_count else 100.0)


@pytest.mark.parametrize(
    ("operator", "amount", "expected_status"),
    [
        ("미만", 3_247_368, "eligible"),
        ("미만", 3_247_369, "ineligible"),
        ("이하", 3_247_369, "eligible"),
        ("초과", 3_247_369, "ineligible"),
        ("초과", 3_247_370, "eligible"),
        ("이상", 3_247_369, "eligible"),
        ("이상", 3_247_368, "ineligible"),
    ],
)
def test_median_income_operators_keep_inclusive_and_exclusive_boundaries(
    operator,
    amount,
    expected_status,
):
    result = _median_income_analysis(
        amount=amount,
        source=f"소득인정액은 기준 중위소득 50% {operator}",
    )

    assert result["status"] == expected_status


@pytest.mark.parametrize(
    ("year", "household_size", "amount", "expected_status"),
    [
        ("2026", 1, 1_282_119, "eligible"),
        ("2026", 2, 2_099_646, "eligible"),
        ("2026", 4, 3_247_369, "eligible"),
        ("2025", 4, 3_247_369, "ineligible"),
    ],
)
def test_median_income_uses_policy_reference_year_and_household_size(
    year,
    household_size,
    amount,
    expected_status,
):
    result = _median_income_analysis(
        amount=amount,
        household_size=household_size,
        reference_year=year,
    )

    assert result["status"] == expected_status


@pytest.mark.parametrize(
    ("amount", "household_size", "reference_year"),
    [
        (None, 4, "2026"),
        ("UNKNOWN", 4, "2026"),
        (1_000_000, None, "2026"),
        (1_000_000, 0, "2026"),
        (1_000_000, 8, "2026"),
        (1_000_000, 4, ""),
        (1_000_000, 4, "2099"),
    ],
)
def test_missing_income_year_or_household_reference_stays_needs_review(
    amount,
    household_size,
    reference_year,
):
    result = _median_income_analysis(
        amount=amount,
        household_size=household_size,
        reference_year=reference_year,
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 1


def test_household_monthly_income_and_personal_income_do_not_replace_income_recognition():
    parsed = EligibilityConditionService.parse_text(
        "소득인정액은 기준 중위소득 50% 이하",
        source_field="selection_criteria",
    )
    condition = WelfareEligibilityCondition(
        serv_id="synthetic-service",
        **next(item for item in parsed if item["condition_type"] == "income_ratio"),
    )
    result = EligibilityMatchingService().analyze_service(
        user=make_user(25),
        service=make_service(),
        conditions=[condition],
        eligibility_conditions={
            "household_size": 4,
            "additional_conditions": {"household_monthly_income_won": 0},
        },
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 1


@pytest.mark.parametrize(
    ("unit", "value_text"),
    [
        ("%", "소득인정액은 기준 중위소득 50% 이하"),
        ("income_recognition", "기준 중위소득 50% 이하"),
    ],
)
def test_legacy_median_income_condition_is_revalidated_for_review(unit, value_text):
    condition = WelfareEligibilityCondition(
        serv_id="synthetic-service",
        condition_type="income_ratio",
        operator="lte",
        value_text=value_text,
        value_number=50,
        upper_value_number=None,
        unit=unit,
        source_field="selection_criteria",
        source_text="소득인정액은 기준 중위소득 50% 이하",
        comparison_ready=True,
        parse_status="parsed",
        confidence=1.0,
    )
    service = make_service()
    service.reference_year = "2026"
    result = EligibilityMatchingService().analyze_service(
        user=make_user(25),
        service=service,
        conditions=[condition],
        eligibility_conditions={
            "household_size": 4,
            "additional_conditions": {"recognized_household_income_won": 1_000_000},
        },
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 1


def test_median_income_gap_and_unrelated_review_keep_policy_b_state():
    parsed = EligibilityConditionService.parse_text(
        "소득인정액은 기준 중위소득 50% 이하",
        source_field="selection_criteria",
    )
    ratio = next(item for item in parsed if item["condition_type"] == "income_ratio")
    conditions = [
        WelfareEligibilityCondition(serv_id="synthetic-service", **ratio),
        WelfareEligibilityCondition(
            serv_id="synthetic-service",
            condition_type="other",
            operator="unknown",
            value_text="별도 심사 조건",
            value_number=None,
            upper_value_number=None,
            unit="",
            source_field="selection_criteria",
            source_text="별도 심사 조건",
            comparison_ready=False,
            parse_status="manual_review",
            confidence=0.0,
        ),
    ]
    service = make_service()
    service.reference_year = "2026"
    result = EligibilityMatchingService().analyze_service(
        user=make_user(25),
        service=service,
        conditions=conditions,
        eligibility_conditions={
            "household_size": 4,
            "additional_conditions": {
                "recognized_household_income_won": 3_247_370,
            },
        },
    )

    assert result["status"] == "needs_review"
    assert len(result["gap_conditions"]) == 1
    assert len(result["review_conditions"]) == 1
    assert result["match_score"] == 0.0


def test_official_2026_two_person_40_percent_threshold_uses_whole_won_rounding():
    from decimal import Decimal

    from app.services.median_income_reference import median_income_threshold

    assert median_income_threshold(2026, 2, Decimal("40")) == 1_679_717


@pytest.mark.parametrize(
    ("profile_value", "expected_display"),
    [("UNKNOWN", "모름·확인 필요"), (None, "미입력")],
)
def test_saved_unknown_and_unentered_additional_statuses_display_differently(
    profile_value,
    expected_display,
):
    condition = WelfareEligibilityCondition(
        serv_id="synthetic-service",
        condition_type="target_group",
        operator="contains",
        value_text="차상위계층 조건",
        value_number=None,
        upper_value_number=None,
        unit="",
        source_field="selection_criteria",
        source_text="차상위계층 조건",
        comparison_ready=False,
        parse_status="manual_review",
        confidence=0.0,
    )
    result = EligibilityMatchingService().analyze_service(
        user=make_user(25),
        service=make_service(),
        conditions=[condition],
        eligibility_conditions={
            "additional_conditions": {"near_poverty_status": profile_value}
        },
    )

    assert result["status"] == "needs_review"
    assert result["review_conditions"][0]["current_value"] == expected_display


@pytest.mark.parametrize(
    "source",
    [
        "기초생활수급자 또는 차상위계층",
        "차상위계층이며 한부모가족 지원대상",
        "차상위계층 제외",
    ],
)
def test_combined_or_and_or_exception_benefit_text_stays_manual(source):
    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )
    target_groups = [
        item for item in parsed if item["condition_type"] == "target_group"
    ]

    assert target_groups
    assert all(not item["comparison_ready"] for item in target_groups)
    assert all(item["parse_status"] == "manual_review" for item in target_groups)


@pytest.mark.parametrize(
    ("amount", "expected_status"),
    [
        (3_247_370, "eligible"),
        (3_247_369, "ineligible"),
        (6_494_738, "eligible"),
        (6_494_739, "ineligible"),
    ],
)
def test_median_income_interval_compares_both_explicit_bounds(
    amount,
    expected_status,
):
    result = _median_income_analysis(
        amount=amount,
        source="소득인정액은 기준 중위소득 50% 초과 100% 이하",
    )

    assert result["status"] == expected_status


def test_explicit_policy_year_overrides_current_year_when_metadata_absent():
    result = _median_income_analysis(
        amount=3_048_887,
        reference_year="",
        source="소득인정액은 2025년 기준 중위소득 50% 이하",
    )

    assert result["status"] == "eligible"


def test_conflicting_policy_year_and_service_reference_stays_needs_review():
    result = _median_income_analysis(
        amount=3_000_000,
        reference_year="2026",
        source="소득인정액은 2025년 기준 중위소득 50% 이하",
    )

    assert result["status"] == "needs_review"
    assert result["gap_conditions"] == []
    assert len(result["review_conditions"]) == 1


def test_current_year_phrase_uses_current_applicable_year_data():
    from decimal import Decimal

    from app.services.median_income_reference import (
        CURRENT_APPLICABLE_YEAR,
        median_income_threshold,
    )

    amount = median_income_threshold(
        CURRENT_APPLICABLE_YEAR,
        4,
        Decimal("50"),
    )
    assert amount is not None
    result = _median_income_analysis(
        amount=amount,
        reference_year="",
        source="소득인정액은 당해년도 기준 중위소득 50% 이하",
    )

    assert result["status"] == "eligible"
