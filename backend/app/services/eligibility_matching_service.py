
from collections import defaultdict
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.welfare_eligibility_condition import (
    WelfareEligibilityCondition,
)
from app.models.welfare_service import WelfareService
from app.schemas.user import EmploymentStatus
from app.services.eligibility_condition_service import (
    EligibilityConditionService,
)
from app.services.median_income_reference import (
    median_income_threshold,
    resolve_policy_reference_year,
)


class EligibilityMatchingService:
    """사용자 프로필과 복지서비스 자격 조건을 비교한다."""

    REVIEW_TYPES = {
        "income_amount",
        "income_ratio",
        "region",
        "employment",
        "target_group",
        "other",
    }
    RECOMMENDATION_AMBIGUITY_PATTERN = re.compile(
        r"(?:또는|혹은|거나|아니면|하나라도|중\s*어느\s*하나|중\s*하나|택일|대안|다만|단\s*,|예외|제외|별도\s*심사)"
    )
    OR_CONNECTOR_PATTERN = re.compile(r"또는|혹은|거나|아니면")

    PROFILE_VALUE_LABELS = {
        "YES": "예",
        "NO": "아니요",
        "MALE": "남성",
        "FEMALE": "여성",
        "SINGLE": "미혼",
        "MARRIED": "기혼",
        "DIVORCED": "이혼",
        "WIDOWED": "사별",
        "EMPLOYED": "취업",
        "EMPLOYED_SME": "중소기업 재직",
        "PART_TIME": "시간제 근로",
        "UNEMPLOYED": "미취업",
        "STUDENT": "학생",
        "SELF_EMPLOYED": "자영업",
        "FREELANCER": "프리랜서",
        "OTHER": "기타",
        "LABOR": "근로소득",
        "BUSINESS": "사업소득",
        "LIVELIHOOD": "생계급여",
        "MEDICAL": "의료급여",
        "HOUSING": "주거급여",
        "EDUCATION": "교육급여",
        "NONE": "해당 없음",
    }

    PROFILE_FIELD_MARKERS = {
        "household_size": ("가구원", "가구 인원", "인 가구"),
        "owns_home": ("주택 소유", "주택 보유", "무주택", "자가"),
        "housing_type": ("주거 형태", "주거유형", "주택 유형"),
        "disability_status": ("장애",),
        "student_status": ("학생",),
        "marital_status": ("혼인", "결혼", "미혼", "기혼"),
        "children_count": ("자녀",),
        "asset_range": ("재산", "자산"),
        "gender": ("성별", "남성", "여성"),
        "qualifications": ("자격 목록",),
        "basic_benefit_status": ("기초생활보장급여 수급", "기초생활수급"),
        "basic_benefit_types": ("생계급여", "의료급여", "주거급여", "교육급여"),
        "near_poverty_status": ("차상위계층", "차상위 계층"),
        "single_parent_support_status": ("한부모가족 지원",),
        "household_monthly_income_won": ("가구 전체 월소득", "가구 월소득"),
        "household_income_recognition_known": ("소득인정액 확인 여부",),
        "recognized_household_income_won": ("소득인정액",),
        "household_basic_benefit_status": ("가구 내 수급자", "가구원 중 수급자"),
        "child_welfare_protection_experience": ("아동복지시설", "가정위탁 보호 경험"),
        "protection_ended": ("보호 종료 여부", "보호종료 여부"),
        "protection_end_month": ("보호 종료 연월", "보호종료 연월"),
        "protection_duration_months": ("보호 기간",),
        "job_seek_registration": ("구직 등록", "구직등록"),
        "employment_support_program": ("취업지원 프로그램",),
        "self_sufficiency_program_status": ("자활사업 참여", "자활사업 참여 여부"),
        "registered_address_sido": ("주민등록상 주소", "주민등록 주소"),
        "registered_residence_start_month": ("거주 시작일", "거주 시작 월"),
    }

    @classmethod
    def _display_profile_value(cls, value) -> str | None:
        if value is None:
            return None

        if isinstance(value, bool):
            return "예" if value else "아니요"

        if isinstance(value, str):
            normalized = value.strip()
            if not normalized or normalized.casefold() == "unknown":
                return None
            return cls.PROFILE_VALUE_LABELS.get(
                normalized.upper(),
                normalized,
            )

        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, (list, dict)):
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            )

        return None

    @classmethod
    def _profile_field_for_condition(
        cls,
        condition: WelfareEligibilityCondition,
    ) -> str | None:
        if condition.condition_type not in {"other", "target_group"}:
            return None

        text = (condition.value_text or "").casefold()
        matched_fields = [
            field
            for field, markers in cls.PROFILE_FIELD_MARKERS.items()
            if any(marker.casefold() in text for marker in markers)
        ]
        return matched_fields[0] if len(matched_fields) == 1 else None

    @classmethod
    def _current_profile_value(
        cls,
        user: User,
        condition: WelfareEligibilityCondition,
        eligibility_conditions: dict[str, Any] | None,
    ) -> str | None:
        profile = (
            eligibility_conditions
            if isinstance(eligibility_conditions, dict)
            else {}
        )
        additional = profile.get("additional_conditions")
        if isinstance(additional, dict):
            profile = {**profile, **additional}

        if condition.condition_type == "region":
            return cls._display_profile_value(user.region)

        if condition.condition_type == "employment":
            additional = profile.get("additional_conditions")
            detail = (
                additional.get("employment_detail")
                if isinstance(additional, dict)
                else None
            )
            return (
                cls._display_profile_value(detail)
                or cls._display_profile_value(user.employment_status)
            )

        if condition.condition_type == "income_amount":
            amount = cls._display_profile_value(user.income_level)
            return f"본인 월 소득 {int(user.income_level):,}원" if amount else None

        if condition.condition_type == "income_ratio":
            if condition.unit != "income_recognition":
                return None
            additional = profile.get("additional_conditions")
            income = (
                additional.get("recognized_household_income_won")
                if isinstance(additional, dict)
                else None
            )
            household_size = profile.get("household_size")
            if income is None or income == "":
                displayed_income = "미입력"
            elif isinstance(income, str) and income.strip().upper() == "UNKNOWN":
                displayed_income = "모름·확인 필요"
            elif isinstance(income, int) and not isinstance(income, bool):
                displayed_income = f"{income:,}원"
            else:
                displayed_income = "확인 필요"
            displayed_size = (
                f"{household_size}인 가구"
                if isinstance(household_size, int)
                and not isinstance(household_size, bool)
                and household_size > 0
                else "가구원 수 미입력"
            )
            return f"가구 소득인정액 {displayed_income} · {displayed_size}"

        profile_field = (
            condition.unit
            if condition.condition_type == "target_group"
            and condition.unit in cls.PROFILE_FIELD_MARKERS
            else cls._profile_field_for_condition(condition)
        )
        if profile_field is None:
            return None

        if profile_field not in profile:
            return None

        raw_value = profile[profile_field]
        if raw_value is None or (
            isinstance(raw_value, str) and not raw_value.strip()
        ):
            return "미입력"
        if isinstance(raw_value, str) and raw_value.strip().upper() == "UNKNOWN":
            return "모름·확인 필요"

        value = cls._display_profile_value(raw_value)
        if value is None:
            return None

        if profile_field == "basic_benefit_types" and isinstance(
            profile.get(profile_field), list
        ):
            values = profile[profile_field]
            return ", ".join(
                cls.PROFILE_VALUE_LABELS.get(str(item), str(item))
                for item in values
            ) or "미입력"

        if profile_field in {"household_size", "children_count"}:
            return f"{value}명"
        return value

    @staticmethod
    def _compare_profile_condition(
        user: User,
        condition: WelfareEligibilityCondition,
        eligibility_conditions: dict[str, Any] | None = None,
    ) -> bool | None:
        if not condition.comparison_ready or condition.parse_status != "parsed":
            return None

        if condition.condition_type == "employment":
            if (
                condition.operator != "equals"
                or condition.unit != "employment_status"
                or EligibilityConditionService.normalize_simple_employment_requirement(
                    condition.source_text
                )
                != condition.value_text
            ):
                return None

            try:
                current_status = EmploymentStatus(user.employment_status).value
                required_status = EmploymentStatus(condition.value_text).value
            except (TypeError, ValueError):
                return None

            # OTHER는 의미가 포괄적이고 STUDENT는 고용 여부를 나타내지 않아
            # 미취업/재직으로 단정하지 않는다.
            if current_status in {EmploymentStatus.OTHER.value, EmploymentStatus.STUDENT.value}:
                return None
            return current_status == required_status

        if condition.condition_type == "region":
            if (
                condition.operator != "equals"
                or condition.unit != "sido"
                or EligibilityConditionService.normalize_simple_sido_requirement(
                    condition.source_text
                )
                != condition.value_text
            ):
                return None

            required_sido = condition.value_text
            current_sido = (
                EligibilityConditionService.canonical_sido_from_profile_region(
                    user.region
                )
            )
            if current_sido is None:
                return None
            return current_sido == required_sido

        if condition.condition_type == "target_group":
            expected = EligibilityConditionService.normalize_simple_profile_status_requirement(
                condition.source_text
            )
            if (
                condition.operator != "equals"
                or expected != (condition.unit, condition.value_text)
            ):
                return None

            profile = (
                eligibility_conditions
                if isinstance(eligibility_conditions, dict)
                else {}
            )
            additional = profile.get("additional_conditions")
            value = additional.get(condition.unit) if isinstance(additional, dict) else None
            if not isinstance(value, str) or value not in {"YES", "NO"}:
                return None
            return value == condition.value_text

        return None

    @staticmethod
    def _compare_income_ratio(
        condition: WelfareEligibilityCondition,
        service: WelfareService,
        eligibility_conditions: dict[str, Any] | None,
    ) -> bool | None:
        if (
            not condition.comparison_ready
            or condition.parse_status != "parsed"
            or condition.unit != "income_recognition"
            or condition.value_text != condition.source_text
            or condition.operator not in {"lte", "lt", "gte", "gt"}
            or condition.value_number is None
        ):
            return None

        source_text = condition.source_text or ""
        normalized = EligibilityConditionService.normalize_simple_income_ratio_requirement(
            source_text
        )
        if normalized is None:
            return None

        expected_requirements, _ = normalized
        try:
            condition_percentage = Decimal(str(condition.value_number))
            if not condition_percentage.is_finite() or not any(
                operator == condition.operator
                and Decimal(str(percentage)) == condition_percentage
                for operator, percentage in expected_requirements
            ):
                return None
        except (InvalidOperation, ValueError):
            return None

        profile = (
            eligibility_conditions
            if isinstance(eligibility_conditions, dict)
            else {}
        )
        additional = profile.get("additional_conditions")
        if isinstance(additional, dict):
            profile = {**profile, **additional}

        household_size = profile.get("household_size")
        recognized_income = profile.get("recognized_household_income_won")
        if (
            not isinstance(household_size, int)
            or isinstance(household_size, bool)
            or household_size < 1
            or not isinstance(recognized_income, int)
            or isinstance(recognized_income, bool)
            or recognized_income < 0
        ):
            return None

        year = resolve_policy_reference_year(
            source_text=source_text,
            service_reference_year=service.reference_year,
        )
        if year is None:
            return None

        threshold = median_income_threshold(
            year=year,
            household_size=household_size,
            percentage=condition_percentage,
        )
        if threshold is None:
            return None

        if condition.operator == "lte":
            return recognized_income <= threshold
        if condition.operator == "lt":
            return recognized_income < threshold
        if condition.operator == "gte":
            return recognized_income >= threshold
        if condition.operator == "gt":
            return recognized_income > threshold
        return None

    @classmethod
    def _age_conditions_needing_review(
        cls,
        conditions: list[WelfareEligibilityCondition],
    ) -> set[int]:
        age_conditions_by_source = defaultdict(list)
        age_conditions_by_field = defaultdict(list)

        for condition in conditions:
            if condition.condition_type == "age" and condition.source_text:
                age_conditions_by_field[condition.source_field].append(condition)
                age_conditions_by_source[
                    (condition.source_field, condition.source_text)
                ].append(condition)

        review_condition_ids = set()

        # 파서가 줄이나 문장 단위로 나누면 관계 연결어가 source_text 밖으로
        # 분리될 수 있다. 같은 원문 필드의 복수 연령 조건은 독립 필수조건으로
        # 단정하지 않고 검토 대상으로 보낸다.
        for age_conditions in age_conditions_by_field.values():
            source_texts = {condition.source_text for condition in age_conditions}
            if len(source_texts) > 1:
                review_condition_ids.update(
                    id(condition) for condition in age_conditions
                )

        for (_, source_text), age_conditions in age_conditions_by_source.items():
            if len(age_conditions) < 2:
                continue

            spans = []
            for condition in age_conditions:
                value_text = condition.value_text or ""
                start = source_text.find(value_text) if value_text else -1
                if start >= 0:
                    spans.append((start, start + len(value_text), condition))

            spans.sort(key=lambda span: (span[0], span[1]))
            has_or_between_age_conditions = any(
                left_end <= right_start
                and cls.OR_CONNECTOR_PATTERN.search(
                    source_text[left_end:right_start]
                )
                for (_, left_end, _), (right_start, _, _) in zip(
                    spans,
                    spans[1:],
                )
            )

            if has_or_between_age_conditions:
                review_condition_ids.update(
                    id(condition) for condition in age_conditions
                )

        return review_condition_ids

    @staticmethod
    def _compare_age(
        user_age: int,
        condition: WelfareEligibilityCondition,
    ) -> bool | None:
        value = condition.value_number
        upper = condition.upper_value_number

        if value is None:
            return None

        if condition.operator == "between":
            if upper is None:
                return None
            return value <= user_age <= upper

        if condition.operator == "gte":
            return user_age >= value

        if condition.operator == "gt":
            return user_age > value

        if condition.operator == "lte":
            return user_age <= value

        if condition.operator == "lt":
            return user_age < value

        return None

    @staticmethod
    def _condition_result(
        condition: WelfareEligibilityCondition,
        status: str,
        current_value: str,
        required_value: str,
        message: str,
        action_guide: str,
    ) -> dict:
        return {
            "condition_type": condition.condition_type,
            "status": status,
            "current_value": current_value,
            "required_value": required_value,
            "message": message,
            "action_guide": action_guide,
            "source_field": condition.source_field,
            "source_text": condition.source_text,
        }

    @classmethod
    def _recommendation_metadata(
        cls,
        evaluated: list[dict],
        gaps: list[dict],
        review: list[dict],
        conditions: list[WelfareEligibilityCondition],
    ) -> dict[str, Any]:
        confirmed = [item for item in evaluated if item["status"] == "passed"]
        ambiguous_source = any(
            cls.RECOMMENDATION_AMBIGUITY_PATTERN.search(
                condition.source_text or ""
            )
            for condition in conditions
        )
        source_groups = {
            (condition.source_field, condition.source_text or "")
            for condition in conditions
            if condition.condition_type != "informational"
        }
        multiple_source_groups = len(source_groups) > 1

        if not evaluated:
            return {
                "recommendation_status": "additional_review",
                "recommendation_reason": (
                    "현재 정보로 자동 비교할 수 있는 조건이 확인되지 않았습니다."
                ),
                "recommendation_uncertainty": None,
                "confirmed_conditions": confirmed,
            }

        if not gaps and not review and confirmed and not ambiguous_source:
            return {
                "recommendation_status": "priority_recommendation",
                "recommendation_reason": (
                    "자동 비교가 가능한 조건을 모두 충족했고 추가 확인 조건이 없습니다."
                ),
                "recommendation_uncertainty": None,
                "confirmed_conditions": confirmed,
            }

        if not gaps and review and confirmed:
            return {
                "recommendation_status": "priority_consideration",
                "recommendation_reason": (
                    "확인 가능한 조건은 충족했으며, 남은 조건은 별도 확인이 필요합니다."
                ),
                "recommendation_uncertainty": (
                    "추가 확인 조건이 핵심 자격요건인지 현재 데이터만으로 판별할 수 없습니다."
                ),
                "confirmed_conditions": confirmed,
            }

        if gaps and not review:
            selection_criteria_gaps = all(
                item["source_field"] == "selection_criteria"
                for item in gaps
            )
            if (
                selection_criteria_gaps
                and not ambiguous_source
                and not multiple_source_groups
            ):
                return {
                    "recommendation_status": "condition_mismatch",
                    "recommendation_reason": (
                        "선정 기준 원문에서 자동 비교한 조건 중 미충족 항목이 확인되었습니다."
                    ),
                    "recommendation_uncertainty": None,
                    "confirmed_conditions": confirmed,
                }

        return {
            "recommendation_status": "additional_review",
            "recommendation_reason": (
                "조건의 필수 여부 또는 조건 간 관계를 현재 정보만으로 안전하게 확정할 수 없습니다."
            ),
            "recommendation_uncertainty": (
                "미충족·추가 확인 조건의 적용 관계를 공식 안내에서 확인해야 합니다."
                if gaps or review or ambiguous_source or multiple_source_groups
                else None
            ),
            "confirmed_conditions": confirmed,
        }

    def analyze_service(
        self,
        user: User,
        service: WelfareService,
        conditions: list[WelfareEligibilityCondition],
        eligibility_conditions: dict[str, Any] | None = None,
    ) -> dict:
        evaluated = []
        gaps = []
        review = []
        notes = []
        age_condition_ids_needing_review = self._age_conditions_needing_review(
            conditions
        )

        for condition in conditions:
            if condition.condition_type == "informational":
                if condition.value_text:
                    notes.append(condition.value_text)
                continue

            if condition.condition_type == "external_review":
                review.append(
                    self._condition_result(
                        condition=condition,
                        status="needs_review",
                        current_value="자동 판정 불가",
                        required_value=condition.value_text,
                        message=(
                            "외부 기관의 심사 기준에 따라 "
                            "결과가 달라질 수 있습니다."
                        ),
                        action_guide=(
                            "해당 기관에 세부 심사 기준을 확인하세요."
                        ),
                    )
                )
                continue

            if id(condition) in age_condition_ids_needing_review:
                review.append(
                    self._condition_result(
                        condition=condition,
                        status="needs_review",
                        current_value=f"{user.age}세",
                        required_value=condition.value_text,
                        message=(
                            "연령 조건 사이의 논리 관계가 불확실해 "
                            "각 조건을 독립 기준으로 판정하지 않습니다."
                        ),
                        action_guide=(
                            "연령 조건의 적용 관계를 서비스 담당 기관에 "
                            "확인하세요."
                        ),
                    )
                )
                continue

            #특정 연령대에 대한 예외적 참여 가능 조항은 일반적인 필수 연령 조건으로 단정하지 않는다.
            source_text = condition.source_text or ""

            is_discretionary_age_clause = (
                condition.condition_type == "age"
                and "경우" in source_text
                and any(
                    phrase in source_text
                    for phrase in (
                        "참여 가능",
                        "판단에 따라",
                        "종합적으로 고려",
                    )
                )
            )

            if is_discretionary_age_clause:
                review.append(
                    self._condition_result(
                        condition=condition,
                        status="needs_review",
                        current_value=f"{user.age}세",
                        required_value=condition.value_text,
                        message=(
                            "연령 조건이 예외적 참여 가능 조항에 포함되어 "
                            "있어 필수 자격 기준으로 단정할 수 없습니다."
                        ),
                        action_guide=(
                            "서비스 담당 기관에 해당 연령 조건의 적용 여부를 "
                            "확인하세요."
                        ),
                    )
                )
                continue

            if condition.condition_type in {"region", "employment", "target_group"}:
                comparison = self._compare_profile_condition(
                    user,
                    condition,
                    eligibility_conditions,
                )
                if comparison is not None:
                    current_value = (
                        self._current_profile_value(
                            user=user,
                            condition=condition,
                            eligibility_conditions=eligibility_conditions,
                        )
                        or "추가 정보 또는 비교 규칙 필요"
                    )
                    result = self._condition_result(
                        condition=condition,
                        status="passed" if comparison else "failed",
                        current_value=current_value,
                        required_value=condition.source_text or condition.value_text,
                        message=(
                            "저장된 프로필 정보가 조건과 일치합니다."
                            if comparison
                            else "저장된 프로필 정보가 조건과 일치하지 않습니다."
                        ),
                        action_guide=(
                            "공식 신청 안내에서 세부 기준을 확인하세요."
                            if comparison
                            else "공식 신청 안내에서 적용 기준과 예외를 확인하세요."
                        ),
                    )
                    evaluated.append(result)
                    if not comparison:
                        gaps.append(result)
                    continue

            if condition.condition_type == "income_ratio":
                comparison = self._compare_income_ratio(
                    condition=condition,
                    service=service,
                    eligibility_conditions=eligibility_conditions,
                )
                if comparison is not None:
                    current_value = (
                        self._current_profile_value(
                            user=user,
                            condition=condition,
                            eligibility_conditions=eligibility_conditions,
                        )
                        or "추가 정보 또는 비교 규칙 필요"
                    )
                    result = self._condition_result(
                        condition=condition,
                        status="passed" if comparison else "failed",
                        current_value=current_value,
                        required_value=condition.source_text or condition.value_text,
                        message=(
                            "가구 소득인정액이 기준 중위소득 기준을 충족합니다."
                            if comparison
                            else "가구 소득인정액이 기준 중위소득 기준을 충족하지 않습니다."
                        ),
                        action_guide=(
                            "공식 신청 안내에서 적용 연도와 산정 기준을 확인하세요."
                            if comparison
                            else "공식 신청 안내에서 소득 산정 및 예외 기준을 확인하세요."
                        ),
                    )
                    evaluated.append(result)
                    if not comparison:
                        gaps.append(result)
                    continue

            can_compare_age = (
                condition.condition_type == "age"
                and condition.comparison_ready
                and condition.parse_status == "parsed"
            )
            
            if can_compare_age:
                comparison = self._compare_age(
                    user.age,
                    condition,
                )

                if comparison is None:
                    review.append(
                        self._condition_result(
                            condition=condition,
                            status="needs_review",
                            current_value=f"{user.age}세",
                            required_value=condition.value_text,
                            message=(
                                "연령 조건의 수치 또는 연산자가 "
                                "불완전해 자동 비교할 수 없습니다."
                            ),
                            action_guide="원문 자격 조건을 확인하세요.",
                        )
                    )
                    continue

                result = self._condition_result(
                    condition=condition,
                    status="passed" if comparison else "failed",
                    current_value=f"{user.age}세",
                    required_value=condition.value_text,
                    message=(
                        "연령 조건을 충족합니다."
                        if comparison
                        else "연령 조건을 충족하지 않습니다."
                    ),
                    action_guide=(
                        "별도의 연령 조치는 필요하지 않습니다."
                        if comparison
                        else (
                            "서비스의 연령 기준과 본인의 나이를 "
                            "확인하세요."
                        )
                    ),
                )

                evaluated.append(result)

                if not comparison:
                    gaps.append(result)

                continue

            if (
                condition.condition_type in self.REVIEW_TYPES
                or condition.parse_status == "manual_review"
                or not condition.comparison_ready
            ):
                review.append(
                    self._condition_result(
                        condition=condition,
                        status="needs_review",
                        current_value=(
                            self._current_profile_value(
                                user=user,
                                condition=condition,
                                eligibility_conditions=eligibility_conditions,
                            )
                            or "추가 정보 또는 비교 규칙 필요"
                        ),
                        required_value=condition.value_text,
                        message=(
                            "현재 구현에서는 이 조건을 "
                            "자동으로 판정할 수 없습니다."
                        ),
                        action_guide=(
                            "서비스 상세 자격요건과 필요한 "
                            "추가 정보를 확인하세요."
                        ),
                    )
                )

        passed_count = sum(
            item["status"] == "passed"
            for item in evaluated
        )
        evaluated_count = len(evaluated)

        match_score = (
            round(passed_count / evaluated_count * 100, 1)
            if evaluated_count
            else 0.0
        )

        if gaps and review:
            status = "needs_review"
        elif gaps:
            status = "ineligible"
        elif review or evaluated_count == 0:
            status = "needs_review"
        else:
            status = "eligible"

        recommendation = self._recommendation_metadata(
            evaluated=evaluated,
            gaps=gaps,
            review=review,
            conditions=conditions,
        )

        return {
            "policy_id": service.serv_id,
            "title": service.serv_name,
            "status": status,
            "match_score": match_score,
            "evaluated_conditions": evaluated_count,
            "passed_conditions": passed_count,
            "gap_conditions": gaps,
            "review_conditions": review,
            **recommendation,
            "notes": list(dict.fromkeys(notes)),
            "detail_url": service.detail_url,
        }

    def analyze_user(
        self,
        db: Session,
        user: User,
        eligibility_conditions: dict[str, Any] | None = None,
    ) -> dict:
        services = (
            db.query(WelfareService)
            .order_by(WelfareService.serv_name)
            .all()
        )

        all_conditions = (
            db.query(WelfareEligibilityCondition)
            .all()
        )

        conditions_by_service = defaultdict(list)

        for condition in all_conditions:
            conditions_by_service[condition.serv_id].append(
                condition
            )

        analyses = [
            self.analyze_service(
                user=user,
                service=service,
                conditions=conditions_by_service[service.serv_id],
                eligibility_conditions=eligibility_conditions,
            )
            for service in services
        ]

        eligible = [
            item
            for item in analyses
            if item["status"] == "eligible"
        ]

        service_by_id = {
            service.serv_id: service
            for service in services
        }

        policies = []

        for item in eligible:
            service = service_by_id[item["policy_id"]]

            policies.append(
                {
                    "policy_id": service.serv_id,
                    "title": service.serv_name,
                    "category": (
                        service.interest_categories or "청년 복지"
                    ),
                    "support_amount": "상세 내용 확인",
                    "match_score": item["match_score"],
                }
            )

        return {
            "matched_count": len(policies),
            "policies": policies,
            "evaluated_count": len(analyses),
            "needs_review_count": sum(
                item["status"] == "needs_review"
                for item in analyses
            ),
            "ineligible_count": sum(
                item["status"] == "ineligible"
                for item in analyses
            ),
            "analysis_results": analyses,
        }
