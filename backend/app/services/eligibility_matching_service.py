
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.welfare_eligibility_condition import (
    WelfareEligibilityCondition,
)
from app.models.welfare_service import WelfareService


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

    def analyze_service(
        self,
        user: User,
        service: WelfareService,
        conditions: list[WelfareEligibilityCondition],
    ) -> dict:
        evaluated = []
        gaps = []
        review = []
        notes = []

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
                        current_value="추가 정보 또는 비교 규칙 필요",
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

        if gaps:
            status = "ineligible"
        elif review or evaluated_count == 0:
            status = "needs_review"
        else:
            status = "eligible"

        return {
            "policy_id": service.serv_id,
            "title": service.serv_name,
            "status": status,
            "match_score": match_score,
            "evaluated_conditions": evaluated_count,
            "passed_conditions": passed_count,
            "gap_conditions": gaps,
            "review_conditions": review,
            "notes": list(dict.fromkeys(notes)),
            "detail_url": service.detail_url,
        }

    def analyze_user(
        self,
        db: Session,
        user: User,
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
