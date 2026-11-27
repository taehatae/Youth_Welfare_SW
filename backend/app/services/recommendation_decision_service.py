"""Conservative recommendation layer, independent of Policy B and its score.

Only bounded, revalidated source forms establish program-level gates. A parsed
row, a passed comparison, or a keyword alone does not establish a required gate.
This is deliberately not a general AND/OR/exception interpreter.
"""
import re
import math

from app.models.welfare_eligibility_condition import WelfareEligibilityCondition
from app.models.welfare_service import WelfareService
from app.services.eligibility_condition_service import EligibilityConditionService as Parser


class RecommendationDecisionService:
    RULESET_VERSION = "2026-10-30-recommendation-context-3a-1"
    RELATION_RISK = re.compile(
        r"또는|혹은|아니면|거나|중\s*(?:어느\s*)?하나|하나\s*이상|다만|예외|"
        r"(?:^|[\s,(（※])단(?:[,，:\s]|$)", re.MULTILINE
    )
    TIME_RISK = re.compile(r"신청일|공고일|졸업|종료일|시행일|기준일|\d{4}년\s*기준")
    CONTEXT_REFERENCE = re.compile(
        r"(?:위|이|해당|앞의|상기)\s*(?:조건|요건|연령|기준|내용|사항)|"
        r"(?:에만|경우에\s*한해)\s*적용"
    )
    SAFE_HEADING = re.compile(r"[○ㅇ◦※□\s:：\-]*(?:지원\s*대상|선정\s*기준|자격\s*기준|신청\s*자격)[\s:：]*")
    WARNING = "신청 검토를 위한 예비 추천이며, 최종 수급 자격과 선정 여부는 담당 기관의 심사에 따릅니다."
    # Public WLF00000025 selection_criteria (2026-10-30). This complete
    # bounded form scopes its exceptions to insured employment, overlapping
    # jobs, repeat participation and massage work, not disability registration.
    # Compare the WHOLE form, never infer independence from absent keywords.
    REGISTRATION_INDEPENDENT_SELECTION = (
        "일반형 일자리참여자 선발 기준표 및 지방자치단체 여건에 맞는 기준을 고려하여 우선 선발합니다.(사업참여경력, 장애정도, 소득수준 등을 반영)"
        "※ 참여 이력은 장애인일자리사업 모든 유형 및 타 지역 참여 경험을 포함\n"
        "장애인일자리사업 우수 참여자, 특수학교 및 대학교 졸업예정자 등일 경우 가점으로 반영합니다.\n"
        "아래 경우에 해당 시, 선발에서 제외합니다.\n"
        "국민건강보험 직장가입자(피부양자는 제외) ※ 단, 근로계약서 기준으로 신청 당시 직장가입자 중 근로종료일이 장애인일자리사업 시작 전일 경우 신청 가능\n"
        "사업자등록증이 있는 자\n"
        "정부부처 및 지자체에서 추진 중인 타 재정지원 일자리사업 참여자 ※ 단, 신청 당시 타 재정지원 일자리 근로 종료일이 장애인일자리사업 시작 전임을 입증할 수 있는 근로계약서를 제출하는 경우에 한해 신청 가능\n"
        "장애인일자리사업에 2년 이상 연속으로 참여한 대상자 ※ 단, 반복참여 제한 예외 대상자는 신청 가능\n"
        "최근 1년 이내 장애인일자리사업 참여 중단 조치를 받은 자\n"
        "수행기관 또는 배치기관의 법인, 기관 단체의 대표, 임직원\n"
        "시각장애인안마사 파견사업의 경우 안마원, 안마시술소를 개설하거나 이에 고용된 자 및 개인사업자로서 출장 안마서비스를 제공하는 자 "
        "※ 단, 외부 요구에 의하여 신고 없이 출장 시술을 통해 서비스를 제공하는 자는 가능"
    )

    @classmethod
    def _registration_has_independent_selection(cls, service, row):
        return (
            row.condition_type == "target_group" and row.unit == "disability_status"
            and row.source_field == "target_details"
            and row.source_text == (service.target_details or "").strip()
            and Parser.normalize_simple_employment_requirement(row.source_text) == "UNEMPLOYED"
            and Parser.normalize_simple_profile_status_requirement(row.source_text) == ("disability_status", "YES")
            and re.sub(r"\s+", "", service.selection_criteria or "")
            == re.sub(r"\s+", "", cls.REGISTRATION_INDEPENDENT_SELECTION)
        )

    @staticmethod
    def _row_signature(row):
        def value(key):
            return row.get(key) if isinstance(row, dict) else getattr(row, key)
        return tuple(value(key) for key in (
            "condition_type", "operator", "value_text", "value_number",
            "upper_value_number", "unit", "comparison_ready", "parse_status",
        ))

    @classmethod
    def _source_matches_row(cls, row):
        if row.condition_type == "age" and row.operator == "between":
            bounds = (row.value_number, row.upper_value_number)
            if any(not isinstance(value, (int, float)) or isinstance(value, bool)
                   or not math.isfinite(value) for value in bounds):
                return False
            if bounds[0] > bounds[1]:
                return False
        parsed = Parser.parse_text(row.source_text, row.source_field)
        if any(cls._row_signature(item) == cls._row_signature(row) for item in parsed):
            return True
        # Legacy age exclusions used lt for the prohibited set. The matcher
        # already evaluates the inverse gate; do not invert its result again.
        threshold = Parser.normalize_age_exclusion(row.source_text)
        return (
            row.condition_type == "age" and threshold is not None
            and row.value_number == threshold and row.operator == "lt"
            and row.value_text.replace(" ", "") in {f"만{threshold}세미만", f"{threshold}세미만"}
            and row.unit == "세" and row.comparison_ready and row.parse_status == "parsed"
        )

    @classmethod
    def _standalone_gate(cls, source):
        """Used for preceding context too: never inherit a component heading."""
        text = source.strip(" \t-•·")
        age = re.fullmatch(
            r"(?:만\s*)?\d{1,2}\s*(?:세\s*(?:이상|이하|미만|초과)|[~∼\-–]\s*(?:만\s*)?\d{1,2}\s*세)"
            r"(?:인\s*(?:청년|청소년)(?:을|를)\s*지원합니다)?[.!。]?", text,
        )
        return bool(
            age or Parser._profile_fact(text)
            or Parser.normalize_simple_employment_requirement(text)
            or Parser.normalize_simple_sido_requirement(text)
            or Parser.normalize_age_exclusion(text) is not None
        )

    @staticmethod
    def _applicant_age_sentence(source):
        """A complete program target statement, not an age/subject keyword.

        Numeric predicates are separately checked against the real parser row.
        Do not use this to certify sibling age clauses as independent: their
        AND/OR relationship has not been established.
        """
        return bool(re.fullmatch(
            r"(?:만\s*)?\d{1,2}\s*(?:세\s*(?:이상|이하|미만|초과)|"
            r"[~∼\-–]\s*(?:만\s*)?\d{1,2}\s*세)"
            r"(?:의|인)?\s*청소년(?:을|를)\s*"
            r"(?:지원합니다|대상으로\s*(?:지원합니다|합니다))[.!。]?",
            source.strip(),
        ))

    @staticmethod
    def _non_eligibility_notice(text):
        """Only whole reference/procedure statements, never a label alone."""
        compact = re.sub(r"\s+", "", text.strip(" \t-•·"))
        return bool(re.fullmatch(
            r"지원대상(?:을|(?:의)?내용을?)?참고"
            r"(?:해주시기바랍니다|해주기바랍니다|하시기바랍니다|해주세요|"
            r"하세요|하십시오|해주십시오|바랍니다)?[.!。]?", compact,
        ) or re.fullmatch(
            r"신청(?:방법|안내|절차)[:：](?:20\d{2}년기준)?"
            r"온라인또는방문(?:신청이가능합니다|으로신청합니다)[.!。]?", compact,
        ))

    @classmethod
    def _risk_context(cls, service, row=None):
        text = (
            service.target_details or ""
            if row is not None and cls._registration_has_independent_selection(service, row)
            else "\n".join((service.target_details or "", service.selection_criteria or ""))
        )
        # Drop only positively verified non-eligibility notices from risk
        # detection. Unknown prose and mixed notices retain their full risk.
        return "\n".join(part for part in re.split(r"\n|\*|(?<=[.!?。])\s+", text)
                         if not cls._non_eligibility_notice(part))

    @classmethod
    def _independent_block(cls, text):
        """Positive, bounded evidence that text cannot waive/qualify a gate.

        Unknown prose stays unknown. A growing keyword blacklist cannot prove
        absence of a qualification, even after a complete first sentence.
        Household requirements are NOT compared here, only kept independent.
        """
        if not text.strip():
            return True
        paragraphs = [part.strip(" \t-•·") for part in re.split(r"\n|(?<=[.!?。])\s+", text) if part.strip()]
        for paragraph in paragraphs:
            if cls._non_eligibility_notice(paragraph):
                continue
            if paragraph in {
                "추가 서류 심사가 필요합니다.", "추가 서류 확인이 필요합니다.",
                "추가 기관 심사가 필요합니다.", "담당 기관의 추가 확인이 필요합니다.",
                "지원대상을 참고해주시기 바랍니다.",
            }:
                continue
            if re.fullmatch(r"가구원\s*수는\s*\d+인\s*이상이어야\s*합니다[.!。]?", paragraph):
                continue
            if cls.SAFE_HEADING.fullmatch(paragraph):
                continue
            if cls._standalone_gate(paragraph) and re.search(r"(?:지원합니다|불가합니다)[.!。]?$", paragraph):
                continue
            return False
        return True

    @classmethod
    def _internal_notes_verified(cls, source):
        # Some parser normalizers read only the body before '*'. Re-parsing
        # the same source is therefore not sufficient to certify its notes.
        parts = source.split("*")
        for note in parts[1:]:
            compact = re.sub(r"\s+", "", note)
            if compact == "일자리지원주요직무:행정도우미,전담지원행정도우미,복지서비스지원요원등":
                continue
            if compact == "사업공고문참조" and Parser.normalize_age_exclusion(source) is not None:
                continue
            if not cls._independent_block(note):
                return False
        return True

    @classmethod
    def _context_reason_codes(cls, service, row):
        if row.source_field not in {"target_details", "selection_criteria"}:
            return ["SOURCE_FIELD_NOT_ELIGIBILITY"]
        original = getattr(service, row.source_field, None) or ""
        source = row.source_text or ""
        if not source or original.count(source) != 1:
            return ["SOURCE_NOT_UNIQUELY_LINKED"]
        reasons = []
        if not cls._internal_notes_verified(source):
            reasons.append("INTERNAL_NOTE_UNVERIFIED")
        if row.source_field == "selection_criteria":
            # A detached selection paragraph may describe a component, parent
            # or ranking group. Without explicit structure, certify it only
            # when the identical gate also has verified whole-program target
            # context. This trades coverage for avoiding false exclusions.
            target = service.target_details or ""
            if source not in target:
                reasons.append("SELECTION_SCOPE_NOT_CORROBORATED")
            else:
                target_row = WelfareEligibilityCondition(source_field="target_details", source_text=source)
                if not cls._verified_context(service, target_row):
                    reasons.append("SELECTION_SCOPE_NOT_CORROBORATED")
        if row.source_field == "target_details" and not cls._registration_has_independent_selection(service, row):
            if not cls._independent_block(service.selection_criteria or ""):
                reasons.append("CONTEXT_OTHER_FIELD_UNVERIFIED")
        suffix = original.split(source, 1)[1].strip()
        # Bare labels may be split subject/complement phrases. A complete
        # sentence can have unrelated review text; a fragment cannot certify
        # that its continuation is unrelated without explicit structure.
        if suffix and not re.search(r"(?:합니다|됩니다)[.!。]?(?:\*.*)?$", source, re.DOTALL):
            reasons.append("SOURCE_FRAGMENT_WITH_CONTINUATION")
        if not cls._independent_block(suffix):
            reasons.append("CONTEXT_FOLLOWING_TEXT_UNVERIFIED")
        prefix = original.split(source, 1)[0].strip()
        # A preceding unknown paragraph may govern role/subject/scope. Accept
        # only bounded sibling gates and generic whole-program field headings.
        if not cls._independent_block(prefix):
            reasons.append("CONTEXT_PRECEDING_TEXT_UNVERIFIED")
        return reasons

    @classmethod
    def _verified_context(cls, service, row):
        return not cls._context_reason_codes(service, row)

    @classmethod
    def _metadata(cls, row):
        source = row.source_text or ""
        kind = row.condition_type
        metadata = dict(role="unresolved", subject="unresolved", scope="unresolved",
                        time_basis="unresolved", input_fields=[])
        if kind == "employment":
            metadata["input_fields"] = ["user.employment_status"]
        elif kind == "region":
            metadata["input_fields"] = ["user.region"]
        elif kind == "income_ratio" and row.unit == "income_recognition":
            metadata["input_fields"] = ["eligibility_conditions.household_size",
                "eligibility_conditions.additional_conditions.recognized_household_income_won"]
        family = re.fullmatch(r"등록장애인의\s*(가족|보호자)(?:을|를)\s*지원합니다[.!。]?", source)
        if family:
            metadata.update(role="requirement", subject="family" if family[1] == "가족" else "guardian",
                            scope="program", time_basis="current")
            return metadata
        if kind == "informational" or Parser.is_age_ranking_table(source) or cls._non_eligibility_notice(source):
            metadata["role"] = "preference" if Parser.clause_role(source) == "preference" else "information"
            return metadata
        if kind == "external_review":
            metadata["role"] = "external_review"
            return metadata
        if kind == "age":
            role = Parser.age_clause_role(source, row.value_text or "")
            metadata["input_fields"] = ["user.age"]
            if role == "benefit_component" or row.unit == "benefit_component":
                metadata.update(role="requirement", subject="applicant", scope="benefit_component")
                metadata["input_fields"] = []
                return metadata
            if role == "manual_review" or row.unit == "manual_review":
                metadata["input_fields"] = []
                value = re.sub(r"\s+", "", row.value_text or "")
                compact = re.sub(r"\s+", "", source)
                if value:
                    subject = re.search(re.escape(value) + r"(?:인|의)?(자녀|손자녀|보호자)", compact)
                    if subject:
                        metadata["subject"] = "guardian" if subject[1] == "보호자" else "child"
                return metadata
            if role == "age_exclusion":
                metadata.update(role="exclusion", subject="applicant", scope="program", time_basis="current")
            elif cls._applicant_age_sentence(source) or cls._standalone_gate(source) or (
                Parser.normalize_simple_employment_requirement(source) == "UNEMPLOYED"
                and Parser.normalize_simple_profile_status_requirement(source) == ("disability_status", "YES")
            ):
                metadata.update(role="requirement", subject="applicant", scope="program", time_basis="current")
            # Other age sources, including medical scope and income compounds,
            # require separate verified structure. A default parser role is not proof.
            return metadata
        if kind == "target_group":
            fact = Parser.normalize_simple_profile_status_requirement(source)
            if fact == (row.unit, row.value_text):
                prefix = "eligibility_conditions."
                if row.unit not in {"gender", "disability_status", "student_status"}:
                    prefix += "additional_conditions."
                metadata.update(
                    role="exclusion" if row.value_text == "NO" else "requirement",
                    subject="applicant", scope="program", time_basis="current",
                    input_fields=[prefix + row.unit],
                )
        elif kind == "employment" and Parser.normalize_simple_employment_requirement(source) == row.value_text:
            metadata.update(role="requirement", subject="applicant", scope="program", time_basis="current",
                            input_fields=["user.employment_status"])
        elif kind == "region" and Parser.normalize_simple_sido_requirement(source) == row.value_text:
            metadata.update(role="requirement", subject="applicant", scope="program", time_basis="current",
                            input_fields=["user.region"])
        return metadata

    @classmethod
    def classify(cls, service: WelfareService, conditions: list[WelfareEligibilityCondition],
                 observations: dict[int, str]) -> dict:
        original = cls._risk_context(service)
        # Without a relationship graph, a linked alternative/exception cannot
        # be certified irrelevant to a failing gate. Preserve that uncertainty.
        relationship_unknown = bool(cls.RELATION_RISK.search(original))
        context_unknown = bool(cls.CONTEXT_REFERENCE.search(original))
        time_unknown = bool(cls.TIME_RISK.search(original))
        evidence = []
        for index, row in enumerate(conditions):
            observed = observations.get(id(row))
            result = observed if observed in {"passed", "failed"} else (
                "unknown" if observed == "needs_review" else "not_evaluated"
            )
            metadata = cls._metadata(row)
            # A verified independent block cannot defeat the registration
            # gate. All other gates still retain the full uncertainty checks.
            context = cls._risk_context(service, row)
            row_relationship_unknown = bool(cls.RELATION_RISK.search(context))
            row_context_unknown = bool(cls.CONTEXT_REFERENCE.search(context))
            row_time_unknown = bool(cls.TIME_RISK.search(context))
            reasons = []
            semantic_gate = (
                metadata["role"] in {"requirement", "exclusion"}
                and metadata["subject"] == "applicant" and metadata["scope"] == "program"
            )
            if not semantic_gate:
                reasons.append("ROLE_SUBJECT_OR_SCOPE_NOT_VERIFIED")
            context_reasons = cls._context_reason_codes(service, row)
            if context_reasons:
                reasons.append("ORIGINAL_CONTEXT_NOT_VERIFIED")
                reasons.extend(context_reasons)
            if semantic_gate and not cls._source_matches_row(row):
                reasons.append("SOURCE_PREDICATE_NOT_VERIFIED")
            if semantic_gate and row_time_unknown:
                reasons.append("TIME_BASIS_NOT_VERIFIED")
            if semantic_gate and row_context_unknown:
                reasons.append("FOLLOWING_OR_CROSS_FIELD_QUALIFICATION_UNRESOLVED")
            if row_relationship_unknown and semantic_gate:
                reasons.append("ALTERNATIVE_OR_EXCEPTION_UNRESOLVED")
            semantics_verified = not reasons
            if result not in {"passed", "failed"}:
                reasons.append("NO_VALID_INPUT_COMPARISON")
            evidence.append(dict(
                condition_ref=f"condition-{index + 1}", condition_type=row.condition_type,
                operator=row.operator or "unknown", value_text=row.value_text or "", unit=row.unit or "",
                value_number=row.value_number, upper_value_number=row.upper_value_number,
                source_field=row.source_field, source_text=row.source_text or "",
                comparison_result=result, **metadata, decision_usable=not reasons, reason_codes=reasons,
                semantics_verified=semantics_verified,
                comparison_semantics="eligibility_gate", parser_version=Parser.PARSER_RULESET_VERSION,
                decision_ruleset_version=cls.RULESET_VERSION,
            ))

        verified_failures = [item for item in evidence if item["decision_usable"] and item["comparison_result"] == "failed"]
        verified_passes = [item for item in evidence if item["decision_usable"] and item["comparison_result"] == "passed"]
        # Relevant uncertainty already prevents a row from being certified.
        # Do not invalidate certified passes again with whole-service keywords
        # from a notice/section whose independence has already been verified.
        unresolved_conflict = any(
            item["comparison_result"] == "failed" and not item["decision_usable"] for item in evidence
        )
        warnings = [cls.WARNING]
        if verified_failures:
            decision = "excluded"
            reason = "입력 정보와 전체 사업에 적용되는 명확한 필수·제외 조건의 불일치가 확인됐습니다."
        elif verified_passes and not unresolved_conflict:
            decision = "candidate"
            reason = "입력 정보와 검증 가능한 필수 조건의 일치 근거가 있으며 확정적인 불일치는 확인되지 않았습니다."
            if any(item["comparison_result"] == "unknown" for item in evidence):
                warnings.append("기존 분석에 추가 확인 항목이 남아 있습니다. 신청 전 공식 안내에서 확인하세요.")
        else:
            decision = "unverified"
            reason = "필수 조건의 일치·불일치를 확정할 근거가 부족하거나 대상·범위·대안·예외 관계를 확인해야 합니다."
        if relationship_unknown:
            warnings.append(
                "원문에 대안·예외 관계가 있어 단일 조건으로 추천 또는 제외를 확정하지 않았습니다."
                if decision == "unverified" else
                "다른 항목의 대안·예외는 신청 전에 확인해야 하며, 인증된 일치 근거와 구분됩니다."
                if decision == "candidate" else
                "다른 조건의 대안·예외는 남아 있으나, 해당 예외와 독립적인 필수 조건의 불일치가 확인됐습니다."
            )
        if context_unknown or time_unknown:
            warnings.append("원문의 적용 범위·대상 또는 시간 기준을 추가로 확인해야 합니다.")
        return dict(recommendation_decision=decision, decision_reason=reason,
                    decision_warnings=warnings, decision_evidence=evidence)
