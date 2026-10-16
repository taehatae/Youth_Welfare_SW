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


def test_unrelated_or_connector_does_not_disable_single_age_comparison():
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

    assert result["status"] == "ineligible"
    assert len(result["gap_conditions"]) == 1
    assert result["gap_conditions"][0]["condition_type"] == "age"
    assert len(result["review_conditions"]) == 1
    assert result["review_conditions"][0]["condition_type"] == "other"
