
import re

from sqlalchemy.orm import Session

from app.models.welfare_eligibility_condition import (
    WelfareEligibilityCondition,
)


class EligibilityConditionService:
    """복지서비스 자격 요건 원문을 구조화한다."""

    AGE_PATTERN = re.compile(
        r"(?:만\s*)?(\d{1,2})\s*세\s*"
        r"(이상|초과|이하|미만)"
    )

    AGE_RANGE_PATTERN = re.compile(
        r"(?:만\s*)?(\d{1,2})\s*"
        r"[~∼\-–]\s*"
        r"(?:만\s*)?(\d{1,2})\s*세"
    )

    INCOME_RATIO_PATTERN = re.compile(
        r"(?:기준\s*)?중위소득\s*"
        r"(\d+(?:\.\d+)?)\s*%\s*"
        r"(이하|미만|이상|초과)"
    )

    MONTHLY_INCOME_PATTERN = re.compile(
        r"월(?:평균)?\s*(?:소득|급여)"
        r"[^。\n]{0,30}?"
        r"(\d[\d,]*)\s*(만원|만\s*원|원)"
        r"(?:\s*(이하|미만|이상|초과))?"
    )

    OPERATOR_MAP = {
        "이상": "gte",
        "초과": "gt",
        "이하": "lte",
        "미만": "lt",
    }

    TARGET_GROUP_TERMS = (
        "조건부수급자",
        "일반수급자",
        "기초생활수급자",
        "수급자",
        "차상위계층",
        "차상위 계층",
        "기초생활보장법",
        "장애인",
        "한부모가족",
        "보호대상자",
        "자립준비청년",
    )

    EXTERNAL_REVIEW_TERMS = (
        "금융기관의 여신규정",
        "여신규정",
        "신용등급",
        "보증인 대출요건",
        "대여가 되지 않을 수",
        "대출이 거절될 수",
        "금융기관에 추천",
    )

    INFORMATIONAL_TERMS = (
        "지원대상을 참고해주시기 바랍니다",
        "지원대상을 참고해 주시기 바랍니다",
        "지원대상을 참고하시기 바랍니다",
        "자세한 사항은 문의",
        "자세한 내용은 문의",
    )

    @classmethod
    def parse_text(
        cls,
        text: str,
        source_field: str,
    ) -> list[dict]:
        """원문에서 자격 조건 및 검토 대상 문구를 추출한다."""

        if not text or not text.strip():
            return []

        conditions = []

        lines = [
            line.strip(" \t-•·")
            for line in text.splitlines()
            if line.strip(" \t-•·")
        ]

        # 줄바꿈이 없는 원문도 문장 단위로 나눈다.
        if len(lines) <= 1:
            lines = [
                part.strip()
                for part in re.split(r"(?<=[.!?。])\s+", text)
                if part.strip()
            ]

        for line in lines:
            extracted = []

            # 1. 연령 범위: 예) 19~34세
            age_ranges = list(cls.AGE_RANGE_PATTERN.finditer(line))

            for match in age_ranges:
                lower = int(match.group(1))
                upper = int(match.group(2))

                if lower <= upper:
                    extracted.append({
                        "condition_type": "age",
                        "operator": "between",
                        "value_text": match.group(0),
                        "value_number": float(lower),
                        "upper_value_number": float(upper),
                        "unit": "세",
                        "comparison_ready": True,
                        "parse_status": "parsed",
                        "confidence": 0.95,
                    })

            # 2. 단일 연령 기준
            for match in cls.AGE_PATTERN.finditer(line):
                # 연령 범위 안에서 이미 추출한 숫자는 중복 처리하지 않는다.
                if any(
                    match.start() >= r.start()
                    and match.end() <= r.end()
                    for r in age_ranges
                ):
                    continue

                age = int(match.group(1))

                extracted.append({
                    "condition_type": "age",
                    "operator": cls.OPERATOR_MAP[match.group(2)],
                    "value_text": match.group(0),
                    "value_number": float(age),
                    "upper_value_number": None,
                    "unit": "세",
                    "comparison_ready": True,
                    "parse_status": "parsed",
                    "confidence": 0.95,
                })

            # 3. 기준 중위소득 비율
            # 예) 기준 중위소득 120% 이하
            # 예) 중위소득 50%이하
            for match in cls.INCOME_RATIO_PATTERN.finditer(line):
                percentage = float(match.group(1))

                extracted.append({
                    "condition_type": "income_ratio",
                    "operator": cls.OPERATOR_MAP[match.group(2)],
                    "value_text": match.group(0),
                    "value_number": percentage,
                    "upper_value_number": None,
                    "unit": "%",
                    # 가구원 수 및 적용 연도별 기준 정보가 필요하다.
                    "comparison_ready": False,
                    "parse_status": "parsed",
                    "confidence": 0.95,
                })

            # 4. 명시적인 월 소득 금액
            for match in cls.MONTHLY_INCOME_PATTERN.finditer(line):
                amount = int(match.group(1).replace(",", ""))

                if "만" in match.group(2):
                    amount *= 10_000

                operator_text = match.group(3)

                extracted.append({
                    "condition_type": "income_amount",
                    "operator": (
                        cls.OPERATOR_MAP[operator_text]
                        if operator_text
                        else "unknown"
                    ),
                    "value_text": match.group(0),
                    "value_number": float(amount),
                    "upper_value_number": None,
                    "unit": "원/월",
                    "comparison_ready": operator_text is not None,
                    "parse_status": (
                        "parsed" if operator_text else "manual_review"
                    ),
                    "confidence": 0.85 if operator_text else 0.5,
                })

            # 5. 수급 자격 및 대상 집단
            matched_target_terms = [
                term
                for term in cls.TARGET_GROUP_TERMS
                if term in line
            ]

            if matched_target_terms:
                extracted.append({
                    "condition_type": "target_group",
                    "operator": "contains",
                    "value_text": line,
                    "value_number": None,
                    "upper_value_number": None,
                    "unit": "",
                    # 문장에 해당 용어가 있다고 자격 충족이 확정되지는 않는다.
                    "comparison_ready": False,
                    "parse_status": "manual_review",
                    "confidence": 0.75,
                })

            # 6. 금융기관 등 외부 기관의 심사 조건
            if any(term in line for term in cls.EXTERNAL_REVIEW_TERMS):
                extracted.append({
                    "condition_type": "external_review",
                    "operator": "unknown",
                    "value_text": line,
                    "value_number": None,
                    "upper_value_number": None,
                    "unit": "",
                    "comparison_ready": False,
                    "parse_status": "manual_review",
                    "confidence": 0.85,
                })

            # 7. 단순 안내 문구
            if any(term in line for term in cls.INFORMATIONAL_TERMS):
                extracted.append({
                    "condition_type": "informational",
                    "operator": "unknown",
                    "value_text": line,
                    "value_number": None,
                    "upper_value_number": None,
                    "unit": "",
                    "comparison_ready": False,
                    "parse_status": "parsed",
                    "confidence": 0.90,
                })

            # 8. 취업 상태 관련 표현
            employment_terms = (
                "미취업",
                "무직",
                "실업",
                "재직자",
                "근로자",
                "취업자",
                "구직",
            )

            if any(term in line for term in employment_terms):
                extracted.append({
                    "condition_type": "employment",
                    "operator": "contains",
                    "value_text": line,
                    "value_number": None,
                    "upper_value_number": None,
                    "unit": "",
                    "comparison_ready": False,
                    "parse_status": "manual_review",
                    "confidence": 0.5,
                })

            # 9. 지역 관련 표현
            region_terms = (
                "거주",
                "주민등록",
                "시·도",
                "시도",
                "지역에",
                "지역 내",
            )

            if any(term in line for term in region_terms):
                extracted.append({
                    "condition_type": "region",
                    "operator": "contains",
                    "value_text": line,
                    "value_number": None,
                    "upper_value_number": None,
                    "unit": "",
                    "comparison_ready": False,
                    "parse_status": "manual_review",
                    "confidence": 0.5,
                })

            # 10. 위 규칙으로 분류하지 못한 원문도 보존
            if not extracted:
                extracted.append({
                    "condition_type": "other",
                    "operator": "unknown",
                    "value_text": line,
                    "value_number": None,
                    "upper_value_number": None,
                    "unit": "",
                    "comparison_ready": False,
                    "parse_status": "manual_review",
                    "confidence": 0.0,
                })

            for item in extracted:
                item["source_field"] = source_field
                item["source_text"] = line
                conditions.append(item)

        return conditions

    @classmethod
    def structure_service(
        cls,
        target_details: str,
        selection_criteria: str,
    ) -> list[dict]:
        """대상자 상세 조건과 선정 기준을 각각 분석한다."""

        conditions = []

        conditions.extend(
            cls.parse_text(
                target_details,
                source_field="target_details",
            )
        )

        conditions.extend(
            cls.parse_text(
                selection_criteria,
                source_field="selection_criteria",
            )
        )

        return conditions

    @classmethod
    def replace_conditions(
        cls,
        db: Session,
        serv_id: str,
        target_details: str,
        selection_criteria: str,
    ) -> int:
        """서비스의 기존 구조화 조건을 새 분석 결과로 교체한다."""

        conditions = cls.structure_service(
            target_details=target_details,
            selection_criteria=selection_criteria,
        )

        db.query(WelfareEligibilityCondition).filter(
            WelfareEligibilityCondition.serv_id == serv_id
        ).delete(synchronize_session=False)

        for item in conditions:
            db.add(
                WelfareEligibilityCondition(
                    serv_id=serv_id,
                    **item,
                )
            )

        # 실제 commit은 호출하는 동기화 서비스에서 수행한다.
        db.flush()

        return len(conditions)
