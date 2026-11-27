"""Bounded semantic extraction, independent of persisted flat conditions.

Only full, applicant/program AND clauses are certified. Source offsets are
Unicode code-point [start, end) offsets into the original field. No user data
or database writes belong here. Unsupported clauses remain explicit evidence.
"""
from dataclasses import dataclass, asdict
from functools import lru_cache
from hashlib import sha256
import re


@dataclass(frozen=True)
class SemanticAtom:
    clause_ref: str
    condition_ref: str
    source_field: str
    source_text: str
    source_span: tuple[int, int]
    condition_type: str
    operator: str
    value_number: float | None = None
    upper_value_number: float | None = None
    value_text: str = ""
    unit: str = ""
    role: str = "requirement"
    subject: str = "applicant"
    scope: str = "program"
    time_basis: str = "current"
    validation: str = "bounded_full_clause"
    reason_codes: tuple[str, ...] = ()
    comparison_source: str = ""


@dataclass(frozen=True)
class SemanticClause:
    clause_ref: str
    source_text: str
    source_field: str
    source_span: tuple[int, int]
    relation: str
    atoms: tuple[SemanticAtom, ...]
    reason_codes: tuple[str, ...] = ()


class SemanticConditionService:
    VERSION = "2026-10-30-semantic-registered-2"
    CERTIFIED_FORMS = {'bounded_full_clause', 'registered_target_clause'}
    REGISTERED = re.compile(
        r'(?P<age>(?:만\s*)?(?P<age_number>\d{1,2})\s*세\s*이상)\s*'
        r'(?:「장애인복지법」상\s*)?(?P<registration>등록(?:된\s*)?)'
        r'(?:(?P<employment>미취업)\s*|(?P<disability_type>지적\s*및\s*자폐성)\s*)?'
        r'장애인(?:을|를)\s*(?:대상으로\s*합니다|지원합니다)[.!。]?'
        r'(?:\s*\*\s*(?P<note>.*))?'
    )
    AGE = r"(?:만\s*)?(?P<lower>\d{1,2})세\s*이상(?:\s*(?P<upper>\d{1,2})세\s*이하)?"
    INCOME = r"(?P<income>(?:가구\s*소득인정액이\s*)?기준\s*중위소득\s*\d+(?:\.\d+)?%\s*(?:이하|미만|이상|초과))"
    # Full match, including the ending, is deliberately stricter than legacy
    # extraction. No substring keyword grants applicant/program authority.
    COMPOUND = re.compile(
        r"(?P<age>" + AGE + r")(?:의|인)?\s*"
        r"(?:(?P<employment>미취업\s*청년|미취업자)\s*|청년\s*)"
        r"(?:(?:중|이며|으로서)\s*" + INCOME + r")?"
        r"(?:인\s*자|(?:을|를)\s*대상으로\s*합니다|(?:을|를)\s*지원합니다)[.!]?"
    )

    @classmethod
    @lru_cache(maxsize=512)
    def decompose(cls, text: str, source_field: str = "target_details") -> tuple[SemanticClause, ...]:
        clauses = []
        for line in re.finditer(r"[^\r\n]+", text or ""):
            raw = line.group()
            stripped = raw.strip()
            offset = line.start() + len(raw) - len(raw.lstrip())
            ref = "clause-" + sha256((cls.VERSION + source_field + str(offset) + raw).encode()).hexdigest()[:20]
            registered = cls.REGISTERED.fullmatch(stripped)
            if registered:
                atoms = []
                for name in ('age', 'registration', 'employment', 'disability_type'):
                    if not registered[name]:
                        continue
                    start, end = registered.span(name)
                    kwargs = {
                        'age': dict(condition_type='age', operator='gte', unit='age',
                            value_number=int(registered['age_number']), value_text=registered['age']),
                        'registration': dict(condition_type='target_group', operator='equals',
                            unit='disability_status', value_text='YES', comparison_source='등록장애인'),
                        'employment': dict(condition_type='employment', operator='equals',
                            unit='employment_status', value_text='UNEMPLOYED', comparison_source='미취업자'),
                        'disability_type': dict(condition_type='target_group', operator='unresolved',
                            unit='disability_type', value_text=registered['disability_type'] or '',
                            reason_codes=('DISABILITY_TYPE_REQUIRES_REVIEW',)),
                    }[name]
                    atoms.append(SemanticAtom(clause_ref=ref, condition_ref=f'semantic-{ref[7:]}-{name}',
                        source_field=source_field, source_text=registered[name],
                        source_span=(offset + start, offset + end), validation='registered_target_clause', **kwargs))
                clauses.append(SemanticClause(ref, stripped, source_field,
                    (offset, offset + len(stripped)), 'AND', tuple(atoms)))
                continue
            match = cls.COMPOUND.fullmatch(stripped)
            if match and (match['employment'] or match['income']):
                atoms = []
                for name in ('age', 'employment', 'income'):
                    if not match[name]:
                        continue
                    source = match[name]
                    start, end = match.span(name)
                    kwargs = {}
                    if name == 'age':
                        lower, upper = int(match['lower']), match['upper']
                        kwargs = dict(condition_type='age', operator='between' if upper else 'gte',
                            value_number=lower, upper_value_number=int(upper) if upper else None,
                            value_text=source, unit='age')
                        if upper and int(upper) < lower:
                            kwargs['reason_codes'] = ('INVALID_AGE_INTERVAL',)
                    elif name == 'employment':
                        kwargs = dict(condition_type='employment', operator='equals',
                            value_text='UNEMPLOYED', unit='employment_status')
                    else:
                        known = source.startswith('가구')
                        operator = {'이하':'lte','미만':'lt','이상':'gte','초과':'gt'}[source[-2:]]
                        kwargs = dict(condition_type='income_ratio', operator=operator,
                            value_number=float(re.search(r'(\d+(?:\.\d+)?)%', source)[1]),
                            value_text=source, unit='income_recognition' if known else 'percent',
                            subject='household' if known else 'unresolved',
                            reason_codes=() if known else ('INCOME_METRIC_UNRESOLVED',))
                    atoms.append(SemanticAtom(clause_ref=ref, condition_ref='semantic-' + ref[7:] + '-' + name,
                        source_field=source_field, source_text=source,
                        source_span=(offset + start, offset + end), **kwargs))
                clauses.append(SemanticClause(ref, stripped, source_field,
                    (offset, offset + len(stripped)), 'AND', tuple(atoms)))
            else:
                relation = 'OR' if re.search(r'또는|혹은|아니면|거나|어느\s*하나', stripped) else 'unresolved'
                # Extraction remains useful even when its relationship/scope
                # cannot be certified. Retain the complete clause as the span;
                # normalized values must never masquerade as exact substrings.
                from app.services.eligibility_condition_service import EligibilityConditionService as Parser
                from app.models.welfare_eligibility_condition import WelfareEligibilityCondition as Condition
                from app.services.recommendation_decision_service import RecommendationDecisionService as Decision
                rows = Parser.structure_service(stripped, '')
                atoms = []
                for index, row in enumerate(rows):
                    metadata = Decision._metadata(Condition(**row))
                    atoms.append(SemanticAtom(clause_ref=ref,
                        condition_ref=f'semantic-{ref[7:]}-{index}', source_field=source_field,
                        source_text=stripped, source_span=(offset, offset + len(stripped)),
                        condition_type=row['condition_type'], operator=row.get('operator') or 'unknown',
                        value_number=row.get('value_number'), upper_value_number=row.get('upper_value_number'),
                        value_text=row.get('value_text') or '', unit=row.get('unit') or '',
                        role=metadata['role'], subject=metadata['subject'], scope=metadata['scope'],
                        time_basis=metadata['time_basis'], validation='extracted_not_certified',
                        reason_codes=('CLAUSE_NOT_CERTIFIED',)))
                clauses.append(SemanticClause(ref, stripped, source_field,
                    (offset, offset + len(stripped)), relation, tuple(atoms), ('CLAUSE_NOT_CERTIFIED',)))
        return tuple(clauses)

    @staticmethod
    def _unique_span(original, source):
        """Exact source linkage, not substring similarity or normalized offsets."""
        if not source or original.count(source) != 1:
            return None
        start = original.index(source)
        return start, start + len(source)

    @staticmethod
    def _independent_notice(text):
        from app.services.recommendation_decision_service import RecommendationDecisionService as Decision
        # Never accept arbitrary standalone sibling gates as neutral prose.
        return (Decision._non_eligibility_notice(text) or text.strip() in {
            '추가 서류 확인이 필요합니다.', '추가 서류 심사가 필요합니다.',
            '추가 기관 심사가 필요합니다.', '담당 기관의 추가 확인이 필요합니다.',
        } or bool(re.fullmatch(
            r'지원\s*내용\s*[:：]\s*(?:월\s*)?\d+\s*(?:만\s*)?원(?:을)?\s*지원합니다[.!。]?', text.strip())))

    @staticmethod
    def _training_components_independent(text):
        """Positive component grammar. Exceptions are bounded to attendance.

        Unknown extra lines invalidate the proof; no keyword absence proves
        independence. This certifies only applicant age/registration, not the
        training/allowance criteria themselves.
        """
        lines = [re.sub(r'\s+', '', line).lstrip('-•·') for line in text.splitlines() if line.strip()]
        headings = 0
        for line in lines:
            if re.fullmatch(r"'(?:직업적응|직업능력개발)훈련(?:수당)?'(?:지급)?대상자는다음과같습니다[.!。]?", line):
                headings += 1
                continue
            if not headings:
                return False
            allowed = (
                r'\d+세이상의장애인으로서직업생활및직업환경에대한심리적,기능적인적응력의향상이필요한자',
                r'지원고용,일반취업및상위기관으로이동하기위해서직업적응훈련이필요한자',
                r'[가-힣]+이훈련과정을승인한직업능력개발훈련실시기관에재학중인훈련생으로서',
                r'등록장애인',
                r'실업급여수급자격이없는자-매월단위의출석일수가소정출석일수의\d+%이상인자(?:\(훈련준비금,자격취득수당예외\))?',
            )
            if not any(re.fullmatch(pattern, line) for pattern in allowed):
                return False
        return bool(headings)

    @classmethod
    def _context_reasons(cls, atom, clause, service, target_clauses):
        from app.services.recommendation_decision_service import RecommendationDecisionService as Decision
        from app.models.welfare_eligibility_condition import WelfareEligibilityCondition as Condition
        reasons = []
        if atom.source_field != 'target_details':
            return ['SELECTION_SCOPE_UNVERIFIED']
        if sum(not c.reason_codes for c in target_clauses) != 1:
            reasons.append('CROSS_CLAUSE_RELATION_UNRESOLVED')
        notes_verified = Decision._internal_notes_verified(clause.source_text)
        if atom.validation == 'registered_target_clause':
            # The legacy helper also accepts sibling gates. Such a gate in
            # an attached note is not proven independent of this target.
            notes_verified = all(cls._independent_notice(note.strip()) or
                re.sub(r'\s+', '', note) ==
                '일자리지원주요직무:행정도우미,전담지원행정도우미,복지서비스지원요원등'
                for note in clause.source_text.split('*')[1:])
        if not notes_verified:
            reasons.append('INTERNAL_NOTE_UNVERIFIED')
        for other in target_clauses:
            if other.clause_ref == clause.clause_ref or cls._independent_notice(other.source_text):
                continue
            # A complete income-independence statement cannot waive an age
            # or registration gate. It does not certify any income predicate.
            if atom.validation == 'registered_target_clause' and re.fullmatch(
                r'장애인\s*당사자\s*및\s*가구의\s*소득수준과\s*무관하게\s*신청\s*가능합니다[.!。]?', other.source_text):
                continue
            reasons.append('CROSS_CLAUSE_RELATION_UNRESOLVED')
        selection = service.selection_criteria or ''
        if selection.strip() and not all(cls._independent_notice(line.strip())
                for line in selection.splitlines() if line.strip()):
            registration_row = Condition(condition_type='target_group', unit='disability_status',
                source_field='target_details', source_text=clause.source_text)
            known_job_registration = (atom.unit == 'disability_status' and
                Decision._registration_has_independent_selection(service, registration_row))
            scoped_training = (atom.validation == 'registered_target_clause' and
                atom.unit in {'age', 'disability_status'} and cls._training_components_independent(selection))
            if not known_job_registration and not scoped_training:
                reasons.append('CROSS_FIELD_QUALIFICATION_UNRESOLVED')
        return list(dict.fromkeys(reasons))

    @classmethod
    def _reuse_comparison(cls, atom, service, conditions, observations):
        from app.services.recommendation_decision_service import RecommendationDecisionService as Decision
        matches = []
        original = getattr(service, atom.source_field, '') or ''
        interval = {}
        for index, row in enumerate(conditions):
            observed = observations.get(id(row))
            if observed not in {'passed', 'failed'}:
                continue
            # Reuse the same applicant boolean comparison across a component
            # and program source only for an exact, standalone registration
            # predicate. Its old role/scope certificate is NEVER inherited.
            scalar_registration = (atom.unit == 'disability_status' and
                atom.validation == 'registered_target_clause' and
                row.source_text == '등록장애인' and row.unit == 'disability_status' and
                row.operator == 'equals' and row.value_text == 'YES')
            if row.source_field != atom.source_field and not scalar_registration:
                continue
            original = getattr(service, row.source_field, '') or ''
            span = cls._unique_span(original, row.source_text)
            if (atom.condition_type == 'age' and atom.operator == 'between' and
                    row.condition_type == 'age' and row.unit in {'세', 'age'} and
                    ((row.operator == 'gte' and row.value_number == atom.value_number) or
                     (row.operator == 'lte' and row.value_number == atom.upper_value_number)) and
                    span and span[0] <= atom.source_span[0] <= atom.source_span[1] <= span[1] and
                    Decision._source_matches_row(row)):
                interval.setdefault(row.operator, []).append((observed == 'passed', f'condition-{index + 1}'))
            keys = ('condition_type', 'operator', 'value_number', 'upper_value_number')
            if any(getattr(row, key) != getattr(atom, key) for key in keys):
                continue
            if atom.condition_type == 'age':
                if row.unit not in {'세', 'age'}:
                    continue
            elif row.unit != atom.unit or row.value_text != atom.value_text:
                continue
            same_occurrence = (row.source_field == atom.source_field and span and
                span[0] <= atom.source_span[0] <= atom.source_span[1] <= span[1])
            if (span and (same_occurrence or scalar_registration)
                    and Decision._source_matches_row(row)):
                matches.append((observed == 'passed', f'condition-{index + 1}'))
        if len(matches) == 1:
            return matches[0]
        if not matches and set(interval) == {'gte', 'lte'} and all(len(v) == 1 for v in interval.values()):
            parts = [interval['gte'][0], interval['lte'][0]]
            return all(part[0] for part in parts), [part[1] for part in parts]
        return None, None

    @classmethod
    def _attach_legacy_anchors(cls, output, service, conditions, observations):
        from app.services.recommendation_decision_service import RecommendationDecisionService as Decision
        for index, row in enumerate(conditions):
            observed = observations.get(id(row))
            if observed not in {'passed', 'failed'}:
                continue
            ref = f'condition-{index + 1}'
            if any(e.get('legacy_condition_ref') == ref or ref in e.get('legacy_condition_refs', []) for e in output):
                continue
            original = getattr(service, row.source_field, '') or ''
            span = cls._unique_span(original, row.source_text)
            verified = span is not None and Decision._source_matches_row(row)
            keys = ('source_field', 'source_text', 'condition_type', 'operator',
                    'value_text', 'value_number', 'upper_value_number', 'unit')
            matches = [e for e in output if all(e.get(k) == getattr(row, k) for k in keys)]
            if verified and len(matches) == 1:
                matches[0].update(legacy_condition_ref=ref, comparison_result=observed,
                    comparison_origin='legacy_reuse')
                continue
            # Exact parser predicate and unique source position are required.
            # Linking an observation never upgrades its role/scope confidence.
            output.append(dict(condition_ref='semantic-legacy-' + ref,
                clause_ref='', source_field=row.source_field, source_text=row.source_text or '',
                source_span=list(span) if verified else None, relation='unresolved', affected_condition_refs=[],
                condition_type=row.condition_type, operator=row.operator, unit=row.unit,
                value_text=row.value_text, value_number=row.value_number, upper_value_number=row.upper_value_number,
                **Decision._metadata(row), validation='legacy_observation',
                comparison_result=observed, comparison_origin='legacy_reuse' if verified else 'legacy_unlinked',
                legacy_condition_ref=ref, decision_usable=False,
                reason_codes=['LEGACY_OBSERVATION_NOT_SEMANTIC_CERTIFICATION'] if verified else
                    ['SOURCE_SPAN_OR_PREDICATE_NOT_VERIFIED'], parser_version=cls.VERSION))

    @classmethod
    def evaluate(cls, matcher, service, user, profile, conditions=None, observations=None):
        """Reuse comparators; keep these evaluations out of legacy Policy B arrays."""
        from app.models.welfare_eligibility_condition import WelfareEligibilityCondition as Condition
        conditions = conditions or []
        observations = observations or {}
        target_clauses = cls.decompose(service.target_details or '')
        selection = service.selection_criteria or ''
        clauses = target_clauses + cls.decompose(selection, 'selection_criteria')
        output = []
        for clause in clauses:
            if not clause.atoms:
                output.append(dict(clause_ref=clause.clause_ref, condition_ref=clause.clause_ref,
                    source_field=clause.source_field, source_text=clause.source_text,
                    source_span=list(clause.source_span), relation=clause.relation,
                    affected_condition_refs=[], comparison_result='not_evaluated',
                    decision_usable=False, reason_codes=list(clause.reason_codes), parser_version=cls.VERSION))
            for atom in clause.atoms:
                reasons = list(atom.reason_codes)
                context_reasons = cls._context_reasons(atom, clause, service, target_clauses)
                reasons.extend(context_reasons)
                context_verified = not reasons
                result, legacy_ref = cls._reuse_comparison(atom, service, conditions, observations)
                origin = 'legacy_reuse' if legacy_ref else 'not_attempted'
                if not reasons and result is None:
                    origin = 'semantic_new'
                    row = Condition(condition_type=atom.condition_type, operator=atom.operator,
                        value_text=atom.value_text, value_number=atom.value_number,
                        upper_value_number=atom.upper_value_number, unit=atom.unit,
                        source_field=atom.source_field, source_text=atom.comparison_source or atom.source_text,
                        parse_status='parsed', comparison_ready=True)
                    if atom.condition_type == 'age':
                        if isinstance(user.age, int) and not isinstance(user.age, bool):
                            result = matcher._compare_age(user.age, row)
                    elif atom.condition_type in {'employment', 'target_group'}:
                        result = matcher._compare_profile_condition(user, row, profile)
                    elif atom.condition_type == 'income_ratio':
                        result = matcher._compare_income_ratio(row, service, profile)
                if result is None:
                    reasons.append('NO_VALID_INPUT_COMPARISON' if origin == 'semantic_new' else 'COMPARISON_NOT_ATTEMPTED')
                item = asdict(atom)
                if atom.source_field != 'target_details' and atom.validation in cls.CERTIFIED_FORMS:
                    item.update(scope='unresolved', validation='extracted_not_certified')
                item.update(source_span=list(atom.source_span), reason_codes=reasons,
                    relation=clause.relation, affected_condition_refs=[a.condition_ref for a in clause.atoms],
                    comparison_result='unknown' if result is None else 'passed' if result else 'failed',
                    clause_text=clause.source_text, clause_span=list(clause.source_span),
                    comparison_origin=origin, semantics_verified=context_verified,
                    role_subject_scope_verified=atom.validation in cls.CERTIFIED_FORMS and not context_reasons,
                    comparison_attempted=origin == 'semantic_new',
                    decision_usable=context_verified and result is not None, parser_version=cls.VERSION)
                if legacy_ref:
                    item['legacy_condition_ref'] = legacy_ref[0] if isinstance(legacy_ref, list) else legacy_ref
                    item['legacy_condition_refs'] = legacy_ref if isinstance(legacy_ref, list) else [legacy_ref]
                    item['legacy_comparison_sources'] = [dict(condition_ref=ref,
                        source_field=conditions[int(ref.split('-')[-1]) - 1].source_field,
                        source_text=conditions[int(ref.split('-')[-1]) - 1].source_text,
                        source_span=list(cls._unique_span(
                            getattr(service, conditions[int(ref.split('-')[-1]) - 1].source_field, '') or '',
                            conditions[int(ref.split('-')[-1]) - 1].source_text)))
                        for ref in item['legacy_condition_refs']]
                output.append(item)
        cls._attach_legacy_anchors(output, service, conditions, observations)
        return output

    @staticmethod
    def augment(decision, semantic):
        """Only certified AND evidence can add a decision; legacy proof survives."""
        from app.schemas.welfare import DecisionEvidence
        # Preserve validated single-condition support and the original observed
        # result without re-certifying it from keywords. Unknown flat clauses
        # remain non-usable even when the old comparator produced a number.
        for item in semantic:
            if item.get('validation') != 'extracted_not_certified':
                continue
            matches = [e for e in decision['decision_evidence'] if all(
                e.get(key) == item.get(key) for key in (
                    'source_field', 'source_text', 'condition_type', 'operator',
                    'value_text', 'value_number', 'upper_value_number', 'unit'))]
            if len(matches) == 1:
                old = matches[0]
                item.update(comparison_result=old['comparison_result'],
                    decision_usable=old['decision_usable'], input_fields=old['input_fields'],
                    legacy_condition_ref=old['condition_ref'])
                if old['decision_usable']:
                    item.update(validation='legacy_certificate', reason_codes=old['reason_codes'])
        usable = [e for e in semantic if e['decision_usable'] and e.get('validation') in SemanticConditionService.CERTIFIED_FORMS]
        failures = [e for e in usable if e['comparison_result'] == 'failed']
        passes = [e for e in usable if e['comparison_result'] == 'passed']
        unresolved_conflict = any(e.get('validation') in SemanticConditionService.CERTIFIED_FORMS
            and e['comparison_result'] == 'failed' and not e['decision_usable'] for e in semantic)
        if failures or (passes and not unresolved_conflict and decision['recommendation_decision'] != 'excluded'):
            decision['recommendation_decision'] = 'excluded' if failures else 'candidate'
            decision['decision_reason'] = ('문장 전체에서 확인된 필수 AND 조건과 입력 정보의 불일치가 있습니다.'
                if failures else '명확한 필수 AND 조건 중 입력 정보와 일치하는 근거가 있습니다.')
            decision['decision_warnings'].append('일부 조건의 비교 결과이며 전체 자격 충족이나 선정 보장이 아닙니다. 미확인 세부 요건은 신청 전에 확인하세요.')
        for item in semantic:
            # Legacy evidence already contains these unverified flat rows.
            # Keep their new source linkage in semantic_analysis, not as a
            # second identical public decision evidence entry.
            if item.get('validation') not in SemanticConditionService.CERTIFIED_FORMS:
                continue
            if item.get('comparison_origin') == 'legacy_reuse':
                # The comparison already exists in decision_evidence. Its new
                # role/scope certificate and source links live in semantic_analysis.
                continue
            field = {'age':['user.age'], 'employment':['user.employment_status'],
                'income_ratio':['eligibility_conditions.household_size',
                    'eligibility_conditions.additional_conditions.recognized_household_income_won']}.get(item['condition_type'], [])
            if 'INCOME_METRIC_UNRESOLVED' in item['reason_codes']:
                field = []
            if item['unit'] == 'disability_status':
                field = ['eligibility_conditions.disability_status']
            evidence = {key: value for key, value in item.items() if key in DecisionEvidence.model_fields}
            evidence.update(input_fields=field, semantics_verified=item.get('semantics_verified', False),
                decision_ruleset_version='semantic-registered-2')
            decision['decision_evidence'].append(DecisionEvidence(**evidence).model_dump())
        return decision
