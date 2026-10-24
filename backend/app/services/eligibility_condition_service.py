
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
        r"(?:기준\s*)?중위소득(?:의\s*)?\s*"
        r"(\d+(?:\.\d+)?)\s*%\s*"
        r"(?:를\s*)?(이하|미만|이상|초과)"
    )
    INCOME_RATIO_INTERVAL_PATTERN = re.compile(
        r"(?:기준\s*)?중위소득(?:의\s*)?\s*"
        r"(?P<lower>\d+(?:\.\d+)?)\s*%\s*(?:를\s*)?"
        r"(?P<lower_operator>초과|이상)\s*"
        r"(?P<upper>\d+(?:\.\d+)?)\s*%\s*(?:를\s*)?"
        r"(?P<upper_operator>이하|미만)"
    )
    SIMPLE_INCOME_RATIO_PATTERN = re.compile(
        r"\s*(?:가구\s*)?소득인정액(?:은|이|가|\s*기준)?\s*"
        r"(?:(?P<year>20\d{2})년|(?P<current_year>당해년도|당해 연도|올해))?\s*"
        r"(?:기준\s*)?중위소득(?:의\s*)?\s*"
        r"(?P<percentage>\d+(?:\.\d+)?)\s*%\s*(?:를\s*)?"
        r"(?P<operator>이하|미만|이상|초과)"
        r"(?:\s*(?:한\s*자|하는\s*자|인\s*자|인))?\s*[.!]?\s*"
    )
    SIMPLE_INCOME_RATIO_INTERVAL_PATTERN = re.compile(
        r"\s*(?:가구\s*)?소득인정액(?:은|이|가|\s*기준)?\s*"
        r"(?:(?P<year>20\d{2})년|(?P<current_year>당해년도|당해 연도|올해))?\s*"
        r"(?:기준\s*)?중위소득(?:의\s*)?\s*"
        r"(?P<lower>\d+(?:\.\d+)?)\s*%\s*(?:를\s*)?"
        r"(?P<lower_operator>초과|이상)\s*"
        r"(?P<upper>\d+(?:\.\d+)?)\s*%\s*(?:를\s*)?"
        r"(?P<upper_operator>이하|미만)"
        r"(?:\s*(?:인\s*자|인))?\s*[.!]?\s*"
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

    SIDO_ALIASES = {
        "서울특별시": ("서울특별시", "서울시"),
        "부산광역시": ("부산광역시", "부산시"),
        "대구광역시": ("대구광역시", "대구시"),
        "인천광역시": ("인천광역시", "인천시"),
        "광주광역시": ("광주광역시",),
        "대전광역시": ("대전광역시", "대전시"),
        "울산광역시": ("울산광역시", "울산시"),
        "세종특별자치시": ("세종특별자치시", "세종시"),
        "경기도": ("경기도",),
        "강원특별자치도": ("강원특별자치도",),
        "충청북도": ("충청북도",),
        "충청남도": ("충청남도",),
        "전북특별자치도": ("전북특별자치도",),
        "전라남도": ("전라남도",),
        "경상북도": ("경상북도",),
        "경상남도": ("경상남도",),
        "제주특별자치도": ("제주특별자치도",),
    }
    SIMPLE_EMPLOYMENT_REQUIREMENTS = {
        "미취업자": "UNEMPLOYED",
        "중소기업재직자": "EMPLOYED_SME",
    }
    SIMPLE_PROFILE_STATUS_REQUIREMENTS = {
        "기초생활수급자": ("basic_benefit_status", "YES"),
        "기초생활보장급여수급자": ("basic_benefit_status", "YES"),
        "차상위계층": ("near_poverty_status", "YES"),
        "한부모가족지원대상": ("single_parent_support_status", "YES"),
        "한부모가족지원대상자": ("single_parent_support_status", "YES"),
    }
    PROFILE_LOGIC_RISK_PATTERN = re.compile(
        r"또는|혹은|거나|아니면|및|다만|예외|제외|아닌|재량|"
        r"(?:^|[\s,])단(?:[,\s:]|$)|"
        r"\d+\s*(?:년|개월|주|일)\s*(?:이상|이하|초과|미만|동안|이내)?"
    )

    TARGET_GROUP_TERMS = (
        "조건부수급자",
        "일반수급자",
        "기초생활수급자",
        "기초생활보장급여 수급자",
        "수급자",
        "차상위계층",
        "차상위 계층",
        "기초생활보장법",
        "장애인",
        "한부모가족",
        "한부모가족 지원대상",
        "한부모가족 지원 대상",
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
        "지원대상의 내용을 참고해 주시기 바랍니다",
        "지원대상의 내용을 참고해주시기 바랍니다",
        "자세한 사항은 문의",
        "자세한 내용은 문의",
    )

    RESIDUAL_CONNECTORS = (
        "이며",
        "이고",
        "또는",
        "그리고",
        "및",
        "와",
        "과",
        "인",
    )

    @staticmethod
    def _term_spans(text: str, terms: tuple[str, ...]) -> list[tuple[int, int]]:
        spans = []
        for term in terms:
            spans.extend(
                (match.start(), match.end())
                for match in re.finditer(re.escape(term), text)
            )
        return spans

    @classmethod
    def _has_profile_logic_risk(cls, text: str) -> bool:
        return bool(cls.PROFILE_LOGIC_RISK_PATTERN.search(text))

    @classmethod
    def _has_income_logic_risk(cls, text: str) -> bool:
        without_reference_year = re.sub(
            r"20\d{2}년(?=\s*(?:기준\s*)?중위소득)",
            "",
            text,
        )
        return cls._has_profile_logic_risk(without_reference_year)

    @classmethod
    def normalize_simple_employment_requirement(
        cls,
        text: str | None,
    ) -> str | None:
        if not text or cls._has_profile_logic_risk(text):
            return None

        normalized = re.sub(r"\s+", "", text.strip(" \t-•◈"))
        return cls.SIMPLE_EMPLOYMENT_REQUIREMENTS.get(normalized)

    @classmethod
    def normalize_simple_profile_status_requirement(
        cls,
        text: str | None,
    ) -> tuple[str, str] | None:
        if not text or cls._has_profile_logic_risk(text):
            return None

        normalized = re.sub(r"\s+", "", text.strip(" \t-•◈"))
        return cls.SIMPLE_PROFILE_STATUS_REQUIREMENTS.get(normalized)

    @classmethod
    def normalize_simple_income_ratio_requirement(
        cls,
        text: str | None,
    ) -> tuple[list[tuple[str, float]], int | None] | None:
        if not text or cls._has_income_logic_risk(text):
            return None

        interval = cls.SIMPLE_INCOME_RATIO_INTERVAL_PATTERN.fullmatch(text)
        if interval:
            return (
                [
                    (
                        cls.OPERATOR_MAP[interval.group("lower_operator")],
                        float(interval.group("lower")),
                    ),
                    (
                        cls.OPERATOR_MAP[interval.group("upper_operator")],
                        float(interval.group("upper")),
                    ),
                ],
                int(interval.group("year")) if interval.group("year") else None,
            )

        single = cls.SIMPLE_INCOME_RATIO_PATTERN.fullmatch(text)
        if not single:
            return None

        return (
            [
                (
                    cls.OPERATOR_MAP[single.group("operator")],
                    float(single.group("percentage")),
                )
            ],
            int(single.group("year")) if single.group("year") else None,
        )

    @classmethod
    def normalize_simple_sido_requirement(
        cls,
        text: str | None,
    ) -> str | None:
        if (
            not text
            or cls._has_profile_logic_risk(text)
            # User.region is a user-entered location, not verified resident
            # registration/address evidence.
            or "주민등록" in text
            or not any(marker in text for marker in ("거주", "주민등록"))
        ):
            return None

        compact = re.sub(r"\s+", "", text.strip(" \t-•◈"))
        matches = [
            (alias, canonical)
            for canonical, aliases in cls.SIDO_ALIASES.items()
            for alias in aliases
            for _ in range(compact.count(alias))
        ]
        if len(matches) != 1:
            return None

        alias, canonical = matches[0]
        residual = compact.replace(alias, "", 1)
        allowed_terms = (
            "주민등록상",
            "주민등록을",
            "주민등록",
            "주소지가",
            "주소지",
            "주소",
            "거주지를",
            "거주지",
            "거주하는",
            "거주한",
            "거주자",
            "거주",
            "두고",
            "둔",
            "청년",
            "대상자",
            "대상",
            "에서",
            "에",
            "은",
            "는",
            "이",
            "가",
            "을",
            "를",
            "자",
            "인",
        )
        for term in allowed_terms:
            residual = residual.replace(term, "")

        return canonical if not residual else None

    @classmethod
    def canonical_sido_from_profile_region(
        cls,
        region: str | None,
    ) -> str | None:
        if not region or not isinstance(region, str):
            return None

        normalized = region.strip()
        matches = [
            (alias, canonical)
            for canonical, aliases in cls.SIDO_ALIASES.items()
            for alias in aliases
            if normalized == alias or normalized.startswith(f"{alias} ")
        ]
        if len(matches) != 1:
            return None

        alias, canonical = matches[0]
        remainder = normalized[len(alias):].strip()
        if any(
            other_alias in remainder
            for aliases in cls.SIDO_ALIASES.values()
            for other_alias in aliases
        ):
            return None
        return canonical

    @classmethod
    def _unrecognized_residual(
        cls,
        line: str,
        recognized_spans: list[tuple[int, int]],
    ) -> str:
        covered = [False] * len(line)
        for start, end in recognized_spans:
            for index in range(start, end):
                covered[index] = True

        residual = "".join(
            " " if covered[index] else character
            for index, character in enumerate(line)
        )
        residual = re.sub(r"[\s,，;；:：·•]+", " ", residual).strip()

        connector_pattern = "|".join(
            re.escape(connector)
            for connector in sorted(
                cls.RESIDUAL_CONNECTORS,
                key=len,
                reverse=True,
            )
        )
        residual = re.sub(
            rf"^(?:(?:{connector_pattern})\s*)+",
            "",
            residual,
        )
        residual = re.sub(
            rf"(?:\s*(?:{connector_pattern}))+\s*$",
            "",
            residual,
        ).strip()

        # 연령 조건 뒤에 붙은 일반적인 대상 명칭만 남은 경우는 새 조건으로 보지 않는다.
        if residual in {"청년", "청년층", "대상", "대상자", "자"}:
            return ""

        return residual

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

        profile_logic_risk = cls._has_profile_logic_risk(text)
        employment_candidates = [
            cls.normalize_simple_employment_requirement(line)
            for line in lines
        ]
        region_candidates = [
            cls.normalize_simple_sido_requirement(line)
            for line in lines
        ]
        allow_single_profile_condition = (
            not profile_logic_risk
            and sum(candidate is not None for candidate in employment_candidates)
            + sum(candidate is not None for candidate in region_candidates)
            == 1
        )

        for line_index, line in enumerate(lines):
            extracted = []
            recognized_spans = []

            # 1. 연령 범위: 예) 19~34세
            age_ranges = list(cls.AGE_RANGE_PATTERN.finditer(line))

            for match in age_ranges:
                lower = int(match.group(1))
                upper = int(match.group(2))

                if lower <= upper:
                    recognized_spans.append(match.span())
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

                recognized_spans.append(match.span())
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
            ratio_matches = []
            interval_spans = []
            for match in cls.INCOME_RATIO_INTERVAL_PATTERN.finditer(line):
                interval_spans.append(match.span())
                recognized_spans.append(match.span())
                ratio_matches.extend(
                    [
                        (
                            match.span("lower"),
                            cls.OPERATOR_MAP[match.group("lower_operator")],
                            float(match.group("lower")),
                        ),
                        (
                            match.span("upper"),
                            cls.OPERATOR_MAP[match.group("upper_operator")],
                            float(match.group("upper")),
                        ),
                    ]
                )

            for match in cls.INCOME_RATIO_PATTERN.finditer(line):
                if any(
                    start <= match.start() and match.end() <= end
                    for start, end in interval_spans
                ):
                    continue
                recognized_spans.append(match.span())
                ratio_matches.append(
                    (
                        match.span(),
                        cls.OPERATOR_MAP[match.group(2)],
                        float(match.group(1)),
                    )
                )

            normalized_income_requirements = (
                cls.normalize_simple_income_ratio_requirement(line)
            )
            normalized_ratios = (
                normalized_income_requirements[0]
                if normalized_income_requirements
                else None
            )
            parsed_ratios = [
                (operator, percentage)
                for _, operator, percentage in ratio_matches
            ]
            is_simple_income_ratio = (
                normalized_ratios is not None
                and normalized_ratios == parsed_ratios
                and not cls._has_income_logic_risk(line)
            )
            if is_simple_income_ratio:
                recognized_spans.append((0, len(line)))

            for _, operator, percentage in ratio_matches:
                extracted.append({
                    "condition_type": "income_ratio",
                    "operator": operator,
                    "value_text": line,
                    "value_number": percentage,
                    "upper_value_number": None,
                    "unit": (
                        "income_recognition"
                        if is_simple_income_ratio
                        else "%"
                    ),
                    # 소득인정액으로 명시되고 단순한 기준만 자동 비교한다.
                    "comparison_ready": is_simple_income_ratio,
                    "parse_status": (
                        "parsed" if is_simple_income_ratio else "manual_review"
                    ),
                    "confidence": 0.95 if is_simple_income_ratio else 0.5,
                })

            # 4. 명시적인 월 소득 금액
            for match in cls.MONTHLY_INCOME_PATTERN.finditer(line):
                recognized_spans.append(match.span())
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
            target_group_spans = cls._term_spans(
                line,
                cls.TARGET_GROUP_TERMS,
            )
            matched_target_terms = bool(target_group_spans)

            if matched_target_terms:
                simple_profile_requirement = (
                    cls.normalize_simple_profile_status_requirement(line)
                )
                recognized_spans.extend(target_group_spans)
                extracted.append({
                    "condition_type": "target_group",
                    "operator": (
                        "equals" if simple_profile_requirement else "contains"
                    ),
                    "value_text": (
                        simple_profile_requirement[1]
                        if simple_profile_requirement
                        else line
                    ),
                    "value_number": None,
                    "upper_value_number": None,
                    "unit": (
                        simple_profile_requirement[0]
                        if simple_profile_requirement
                        else ""
                    ),
                    # 단일 표준 표현만 프로필 상태와 비교한다. 사용자 응답은
                    # 공식 증명이 아니며 복합 문구는 계속 수동 검토한다.
                    "comparison_ready": simple_profile_requirement is not None,
                    "parse_status": (
                        "parsed" if simple_profile_requirement else "manual_review"
                    ),
                    "confidence": 0.95 if simple_profile_requirement else 0.75,
                })

            # 6. 금융기관 등 외부 기관의 심사 조건
            external_review_spans = cls._term_spans(
                line,
                cls.EXTERNAL_REVIEW_TERMS,
            )
            if external_review_spans:
                recognized_spans.extend(external_review_spans)
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
            informational_spans = cls._term_spans(
                line,
                cls.INFORMATIONAL_TERMS,
            )
            if informational_spans:
                recognized_spans.extend(informational_spans)
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
            region_terms = (
                "거주",
                "주민등록",
                "시·도",
                "시도",
                "지역에",
                "지역 내",
            )

            normalized_employment = employment_candidates[line_index]
            if allow_single_profile_condition and normalized_employment:
                recognized_spans.append((0, len(line)))
                extracted.append({
                    "condition_type": "employment",
                    "operator": "equals",
                    "value_text": normalized_employment,
                    "value_number": None,
                    "upper_value_number": None,
                    "unit": "employment_status",
                    "comparison_ready": True,
                    "parse_status": "parsed",
                    "confidence": 0.95,
                })
            else:
                employment_spans = cls._term_spans(line, employment_terms)
                if employment_spans:
                    recognized_spans.extend(employment_spans)
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

            normalized_region = region_candidates[line_index]
            if allow_single_profile_condition and normalized_region:
                recognized_spans.append((0, len(line)))
                extracted.append({
                    "condition_type": "region",
                    "operator": "equals",
                    "value_text": normalized_region,
                    "value_number": None,
                    "upper_value_number": None,
                    "unit": "sido",
                    "comparison_ready": True,
                    "parse_status": "parsed",
                    "confidence": 0.95,
                })
            else:
                region_spans = cls._term_spans(line, region_terms)
                if region_spans:
                    recognized_spans.extend(region_spans)
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

            # 10. 인식된 조건 바깥의 잔여 문구도 별도 검토 조건으로 보존한다.
            residual = cls._unrecognized_residual(line, recognized_spans)
            if residual:
                extracted.append({
                    "condition_type": "other",
                    "operator": "unknown",
                    "value_text": residual,
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
