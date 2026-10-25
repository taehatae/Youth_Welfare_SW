
import re
from functools import lru_cache

from sqlalchemy.orm import Session

from app.models.welfare_eligibility_condition import (
    WelfareEligibilityCondition,
)


class EligibilityConditionService:
    """복지서비스 자격 요건 원문을 구조화한다."""

    PARSER_RULESET_VERSION = "2026-10-25-phase-two-1"
    SHORT_SIDO_NAMES = {
        "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
        "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
        "울산": "울산광역시", "세종": "세종특별자치시", "경기": "경기도",
        "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
        "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도",
        "경남": "경상남도", "제주": "제주특별자치도",
    }
    EMPLOYEE_EXCLUSION_HEADINGS = {
        "아래 해당되는 참여자 제외됩니다.",
        "다음에 해당하는 경우에는 사업에 참여할 수 없습니다.",
        "제외 대상:",
    }

    @classmethod
    def explicit_employee_exclusion_source(cls, text: str) -> str | None:
        """Find a literal excluded employee item with its contiguous parent scope."""
        raw_lines = text.splitlines(keepends=True)
        clean = [line.strip(" \t\r\n-•·") for line in raw_lines]
        if clean.count("취업자") != 1:
            return None
        start = None
        offset = 0
        for raw, line in zip(raw_lines, clean):
            if line in cls.EMPLOYEE_EXCLUSION_HEADINGS:
                start = offset
            elif start is not None:
                if line == "취업자":
                    return text[start:offset + len(raw.rstrip("\r\n"))]
                if (
                    re.search(r"또는|혹은|거나|아니면|다만|예외", line)
                    or line.endswith((":", "："))
                    or re.search(r"지원\s*대상|기본\s*자격|우대\s*대상", line)
                    or not line.endswith("자")
                ):
                    return None
            offset += len(raw)
        return None

    @classmethod
    def employment_clause_kind(cls, text: str) -> str:
        """Diagnostic meaning, not a claim that the clause is a required job status."""
        if re.search(r"도시근로자|근로자가구|상시근로자소득|공적이전소득", text):
            return "income_reference"
        if re.search(r"근로자\s*\d+|근로자수|피보험자수|근로자에 대한 재산", text):
            return "employer_workforce"
        if re.search(r"실업급여|구직급여", text):
            return "benefit_entitlement"
        if text.strip() in {"취업자", "(취업자 기준)", "(산업단지근로자)"}:
            return "unscoped_item"
        if "우선" in text:
            return "preference"
        if cls.normalize_simple_employment_requirement(text):
            return "simple_status"
        if re.search(r"또는|혹은|거나|아니면|및|다만|예외|제외", text):
            return "alternative_or_exception"
        return "occupation_or_program"

    @staticmethod
    def region_clause_kind(text: str) -> str:
        if re.search(r"지역.*거주.*취업자|지역.*소재.*사업장|근무지", text):
            return "residence_or_workplace"
        if re.search(r"\d+\s*(?:개월|년).*거주|거주지보호기간|\d+년\s*이상.*등재", text):
            return "residence_duration"
        if re.search(r"주민등록.*(?:가구|가족|세대|동거|자녀|주택)|동일\s*주소지|동거하는", text):
            return "household_or_address"
        if "주민등록" in text:
            return "registered_address"
        if re.search(r"도서|벽지|농어촌|난시청", text):
            return "area_category"
        if "국내" in text:
            return "country_or_nationality"
        if re.search(r"사업지역|시범사업|해당지역|주택건설지역|지역특화", text):
            return "designated_area"
        if re.search(r"거주시설|공공임대주택|비주택|거주공간|전대차|임대차|거주지로 간주", text):
            return "housing_status"
        return "other_context"

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
        "재직중인근로자": "EMPLOYED",
        "미취업자": "UNEMPLOYED",
        "미취업청년": "UNEMPLOYED",
        "실업자": "UNEMPLOYED",
        "중소기업재직자": "EMPLOYED_SME",
        "중소기업재직청년": "EMPLOYED_SME",
    }
    PERSONAL_FACT_REQUIREMENTS = {
        "여성": ("gender", "FEMALE"),
        "남성": ("gender", "MALE"),
        "여성청소년": ("gender", "FEMALE"),
        "등록장애인": ("disability_status", "YES"),
        "재학생": ("student_status", "YES"),
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

        normalized = cls._strip_support_sentence(text)
        if normalized in cls.SIMPLE_EMPLOYMENT_REQUIREMENTS:
            return cls.SIMPLE_EMPLOYMENT_REQUIREMENTS[normalized]
        body = re.sub(r"\s+", "", text.split("*", 1)[0])
        if re.fullmatch(
            r"(?:만)?\d+세이상「장애인복지법」상등록된미취업장애인을대상으로합니다[.!]?",
            body,
        ):
            return "UNEMPLOYED"
        return None

    @staticmethod
    def _strip_support_sentence(text: str) -> str:
        compact = re.sub(r"\s+", "", text.strip(" \t-•◈"))
        return re.sub(r"(?:을|를)(?:대상으로)?지원합니다[.!。]?$", "", compact)

    @classmethod
    def _profile_fact(cls, text: str | None):
        """Return (field/value, whole-clause recognition), never infer an OR group."""
        if not text:
            return None
        compact = re.sub(r"\s+", "", text.strip(" \t-•◈"))
        # Negation is accepted only for an explicit, complete single exclusion.
        exclusion = re.fullmatch(
            r"(등록장애인|재학생)(?:은|는)?(?:지원|참여)대상에서제외합니다[.!。]?",
            compact,
        )
        if exclusion:
            field, _ = cls.PERSONAL_FACT_REQUIREMENTS[exclusion.group(1)]
            return ((field, "NO"), True)
        # Ignore only an explicitly labelled reference year, not exceptions or
        # alternatives appearing in a footnote after the eligibility sentence.
        without_reference_year = re.sub(r"20\d{2}년\s*기준", "", text)
        if cls._has_profile_logic_risk(without_reference_year):
            return None
        normalized = cls._strip_support_sentence(text)
        known = {**cls.SIMPLE_PROFILE_STATUS_REQUIREMENTS, **cls.PERSONAL_FACT_REQUIREMENTS}
        if normalized in known:
            return (known[normalized], True)
        body = re.sub(r"\s+", "", text.split("*", 1)[0])
        # Bounded real-source forms. Keep all other income/age clauses and the
        # footnote as residual; this extracts only the explicit personal fact.
        if re.fullmatch(
            r"가구의소득인정액이「국민기초생활보장법」에의한기준중위소득"
            r"\d+%초과\d+%이하가구의\d+세이상의등록장애인을지원합니다[.!]?",
            body,
        ):
            return (("disability_status", "YES"), False)
        if re.fullmatch(r"자격기준[:：]취약계층\d+[~∼-]\d+세여성청소년", compact):
            return (("gender", "FEMALE"), False)
        return None

    @classmethod
    def clause_role(cls, text: str) -> str:
        """Classify only bounded notice templates; unknown scope stays reviewable."""
        compact = re.sub(r"\s+", "", text).rstrip(".!。:：")
        if compact in {
            "선발일반사항은다음과같습니다",
            "지방산림청장,국유림관리소장및시장,도지사,군수,구청장이선발합니다",
        }:
            return "procedure"
        if compact == "특별한기술,자격및경험을필요로하는사업은경험이있는자를우선고용할수있음":
            # Whether the selected project requires this skill is unknown.
            return "conditional_preference"
        if compact in {
            "우대대상", "우선선발대상", "가점대상",
            "취업취약계층우선선발기준은다음과같습니다",
            "모집·공고시'취업취약계층우선선발'을명시토록하고,선발시취업취약계층지원자에게가점부여등을통해우선선발",
        } or re.fullmatch(
            r"저소득층,장애인,장기실직자,한부모가족등취업취약계층의참여목표인원"
            r"\(\d+(?:\.\d+)?%이상\)을사전확정하여선발및사후관리", compact
        ):
            return "preference"
        if re.search(r"제외|불가|참여할수없|지원할수없|배제", compact):
            return "exclusion"
        fact = cls._profile_fact(text)
        if fact and fact[1]:
            return "requirement"
        return "uncertain"

    @classmethod
    def normalize_simple_profile_status_requirement(
        cls,
        text: str | None,
    ) -> tuple[str, str] | None:
        fact = cls._profile_fact(text)
        return fact[0] if fact else None

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

        compact = cls._strip_support_sentence(text)
        short_sido = re.fullmatch(
            r"(" + "|".join(map(re.escape, cls.SHORT_SIDO_NAMES)) + r")"
            r"(?:에|에서)?(?:거주자|거주하는청년|거주중인청년|거주중인자)",
            compact,
        )
        if short_sido:
            return cls.SHORT_SIDO_NAMES[short_sido.group(1)]
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
        tokens = normalized.split()
        if tokens[0] in cls.SHORT_SIDO_NAMES:
            if any(token in cls.SHORT_SIDO_NAMES for token in tokens[1:]):
                return None
            normalized = " ".join([cls.SHORT_SIDO_NAMES[tokens[0]], *tokens[1:]])
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
        if not any(character.isalnum() for character in residual):
            return ""
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
        profile_fact_candidates = [cls._profile_fact(line) for line in lines]
        allow_single_profile_fact = (
            sum(fact is not None for fact in profile_fact_candidates) == 1
            and not any(re.match(r"^(?:또는|혹은|아니면|다음.*어느\s*하나)", line) for line in lines)
        )

        exclusion_scope = False
        preference_scope = False
        for line_index, line in enumerate(lines):
            extracted = []
            recognized_spans = []
            role = cls.clause_role(line)
            compact_heading = re.sub(r"\s+", "", line).rstrip(".!。:：")
            if role in {"procedure", "preference"}:
                conditions.append({
                    "condition_type": "informational", "operator": "unknown",
                    "value_text": line, "value_number": None, "upper_value_number": None,
                    "unit": role, "comparison_ready": False, "parse_status": "parsed",
                    "confidence": 0.95, "source_field": source_field, "source_text": line,
                })
                exclusion_scope = False
                preference_scope = compact_heading in {"우대대상", "우선선발대상", "가점대상"}
                continue
            if role == "exclusion" and (line in cls.EMPLOYEE_EXCLUSION_HEADINGS or re.fullmatch(
                r".*(?:제외|불가).*대상|다음.*(?:참여|지원)할수없습니다|(?:지원|참여)불가",
                compact_heading,
            )):
                exclusion_scope = True
                preference_scope = False

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
            simple_profile_requirement = (
                cls.normalize_simple_profile_status_requirement(line)
                if not (exclusion_scope or preference_scope) and allow_single_profile_fact else None
            )
            matched_target_terms = bool(target_group_spans) or simple_profile_requirement is not None

            if matched_target_terms:
                recognized_spans.extend(target_group_spans)
                if simple_profile_requirement:
                    fact = cls._profile_fact(line)
                    if fact[1]:
                        recognized_spans.append((0, len(line)))
                    else:
                        recognized_spans.extend(
                            match.span() for match in re.finditer(r"등록\s*장애인|여성청소년", line)
                        )
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
            excluded_employee_source = (
                cls.explicit_employee_exclusion_source(text) if line == "취업자" else None
            )
            if excluded_employee_source:
                recognized_spans.append((0, len(line)))
                extracted.append({
                    "condition_type": "employment", "operator": "not_equals",
                    "value_text": "EMPLOYED", "value_number": None, "upper_value_number": None,
                    "unit": "employment_exclusion", "comparison_ready": True,
                    "parse_status": "parsed", "confidence": 0.95,
                    "source_text": excluded_employee_source,
                })
            elif allow_single_profile_condition and normalized_employment:
                if cls._strip_support_sentence(line) in cls.SIMPLE_EMPLOYMENT_REQUIREMENTS:
                    recognized_spans.append((0, len(line)))
                else:
                    # An embedded job requirement does not account for the
                    # remaining disability criteria or job-description note.
                    recognized_spans.extend(match.span() for match in re.finditer("미취업", line))
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
                    kind = cls.employment_clause_kind(line)
                    non_job_status = kind in {"income_reference", "benefit_entitlement", "employer_workforce"}
                    recognized_spans.extend([(0, len(line))] if non_job_status else employment_spans)
                    extracted.append({
                        "condition_type": "other" if non_job_status else "employment",
                        "operator": "unknown" if non_job_status else "contains",
                        "value_text": line,
                        "value_number": None,
                        "upper_value_number": None,
                        "unit": kind if non_job_status else "",
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
                    kind = cls.region_clause_kind(line)
                    non_geographic = kind in {"household_or_address", "housing_status", "country_or_nationality"}
                    recognized_spans.extend([(0, len(line))] if non_geographic else region_spans)
                    extracted.append({
                        "condition_type": "other" if non_geographic else "region",
                        "operator": "unknown" if non_geographic else "contains",
                        "value_text": line,
                        "value_number": None,
                        "upper_value_number": None,
                        "unit": kind if non_geographic else "",
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
                    "unit": ("exclusion" if exclusion_scope else "preference" if preference_scope
                             else role if role != "uncertain" else ""),
                    "comparison_ready": False,
                    "parse_status": "manual_review",
                    "confidence": 0.0,
                })

            for item in extracted:
                if (
                    (exclusion_scope or preference_scope)
                    and item["comparison_ready"]
                    and item["unit"] != "employment_exclusion"
                ):
                    item["comparison_ready"] = False
                    item["parse_status"] = "manual_review"
                    item["confidence"] = 0.5
                item["source_field"] = source_field
                item.setdefault("source_text", line)
                conditions.append(item)

        return conditions

    @classmethod
    @lru_cache(maxsize=256)
    def cached_structure_service(
        cls, ruleset_version: str, target_details: str, selection_criteria: str,
    ) -> tuple[tuple[tuple[str, object], ...], ...]:
        """Immutable public-source templates only; never cache profiles or decisions.

        Source contents and the explicit ruleset version are cache keys. Each
        request creates fresh ORM objects, so a caller cannot mutate cached rows.
        Bump PARSER_RULESET_VERSION whenever interpretation rules change.
        """
        return tuple(tuple(item.items()) for item in cls.structure_service(target_details, selection_criteria))

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
