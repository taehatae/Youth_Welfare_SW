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

    assert len(income_conditions) == 1
    assert income_conditions[0]["operator"] == "gt"
    assert income_conditions[0]["value_number"] == 50.0
    assert income_conditions[0]["value_text"] == "기준중위소득 50% 초과"
    assert income_conditions[0]["comparison_ready"] is False
    assert len(residual_conditions) == 1
    assert residual_conditions[0]["value_text"] == "100% 이하"
    assert residual_conditions[0]["source_text"] == source
    assert residual_conditions[0]["parse_status"] == "manual_review"
    assert residual_conditions[0]["comparison_ready"] is False


def test_api_excerpt_income_ratio_with_postposition_is_preserved_for_review():
    # 실제 API 발췌: WLF00001138 선정 기준에서 확인한 문구.
    source = "소득인정액이 기준 중위소득의 40%를 초과한 자"

    parsed = EligibilityConditionService.parse_text(
        source,
        source_field="selection_criteria",
    )

    assert not any(item["condition_type"] == "income_ratio" for item in parsed)
    assert any(
        item["condition_type"] == "other"
        and "중위소득의 40%를 초과" in item["value_text"]
        and item["source_text"] == source
        and item["source_field"] == "selection_criteria"
        and item["parse_status"] == "manual_review"
        and item["comparison_ready"] is False
        for item in parsed
    )


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
