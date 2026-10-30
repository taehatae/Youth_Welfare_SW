"""Actual public excerpts, synthetic users; no DB/network in these tests."""
import json
from pathlib import Path

import pytest

from app.models.user import User
from app.models.welfare_service import WelfareService
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition as Condition
from app.services.eligibility_condition_service import EligibilityConditionService as Parser
from app.services.eligibility_matching_service import EligibilityMatchingService as Matcher
from app.services.semantic_condition_service import SemanticConditionService as Semantic

CASES = {c['service_id']: c for c in json.loads((Path(__file__).parent / 'fixtures' /
    'registered_semantic_excerpts.json').read_text(encoding='utf-8'))['services']}


def analyze(case, disability='YES', age=25, employment='UNEMPLOYED'):
    service = WelfareService(serv_id='not-a-policy-id', serv_name='Test', detail_url='',
        target_details=case['target_details'], selection_criteria=case['selection_criteria'])
    rows = [Condition(serv_id=service.serv_id, **row)
            for row in Parser.structure_service(service.target_details, service.selection_criteria)]
    result = Matcher().analyze_service(User(age=age, region='서울', income_level=0,
        employment_status=employment), service, rows, {'disability_status': disability})
    return result


@pytest.mark.parametrize('sid,units', [
    ('WLF00003189', {'age', 'disability_status'}),
    ('WLF00001165', {'age', 'disability_status', 'disability_type'}),
    ('WLF00000025', {'age', 'disability_status', 'employment_status'}),
])
def test_actual_registered_and_is_extracted_with_exact_spans(sid, units):
    case = CASES[sid]
    clause = Semantic.decompose(case['target_details'])[0]
    assert clause.relation == 'AND'
    assert {atom.unit for atom in clause.atoms} == units
    for atom in clause.atoms:
        assert atom.subject == 'applicant'
        assert atom.scope == 'program'
        assert atom.role == 'requirement'
        assert case['target_details'][slice(*atom.source_span)] == atom.source_text


@pytest.mark.parametrize('sid', ['WLF00003189', 'WLF00001165', 'WLF00000025'])
@pytest.mark.parametrize('value,expected', [('NO', 'excluded'), ('YES', 'candidate')])
def test_actual_registered_gate_decisions(sid, value, expected):
    result = analyze(CASES[sid], disability=value)
    assert result['recommendation_decision'] == expected
    registration = [e for e in result['semantic_analysis'] if e.get('unit') == 'disability_status'
                    and e['source_field'] == 'target_details']
    assert len(registration) == 1
    assert registration[0]['decision_usable']


def test_actual_disability_type_is_not_inferred_from_registered_yes():
    result = analyze(CASES['WLF00001165'])
    atom = next(e for e in result['semantic_analysis'] if e.get('unit') == 'disability_type')
    assert atom['comparison_result'] == 'unknown'
    assert not atom['decision_usable']
    assert 'DISABILITY_TYPE_REQUIRES_REVIEW' in atom['reason_codes']
    assert atom['role_subject_scope_verified']


@pytest.mark.parametrize('suffix', [
    '\n다만 미등록 장애인도 의사의 소견이 있으면 신청 가능합니다.',
    '\n위 조건은 신청자의 가족을 기준으로 확인합니다.',
    '\n위 조건은 세부 지원에만 적용합니다.',
    '\n위 연령은 졸업 당시 기준입니다.',
    '* 등록하지 않은 사람도 인정됩니다.',
])
def test_synthetic_qualification_cannot_be_discarded(suffix):
    case = dict(CASES['WLF00003189'], selection_criteria='',
        target_details=CASES['WLF00003189']['target_details'] + suffix)
    assert analyze(case, disability='NO')['recommendation_decision'] == 'unverified'


@pytest.mark.parametrize('prefix', ['자녀 조건: ', '보호자 조건: ', '세부 의료비 지원: ', '우대 기준: ', '연령별 배점: '])
def test_synthetic_non_applicant_or_non_gate_is_not_promoted(prefix):
    case = dict(CASES['WLF00003189'], selection_criteria='',
        target_details=prefix + CASES['WLF00003189']['target_details'])
    assert analyze(case, disability='NO')['recommendation_decision'] == 'unverified'


def test_synthetic_independent_procedure_does_not_invalidate_target():
    case = dict(CASES['WLF00003189'], selection_criteria='추가 서류 확인이 필요합니다.')
    assert analyze(case)['recommendation_decision'] == 'candidate'


@pytest.mark.parametrize('sid,kind', [
    ('WLF00003270', 'age'), ('WLF00003189', 'target_group'),
    ('WLF00006217', 'employment'), ('WLF00006265', 'age'),
])
def test_actual_all_legacy_automatic_comparisons_keep_verified_source_anchor(sid, kind):
    case = CASES[sid]
    result = analyze(case)
    automatic = [e for e in result['decision_evidence'] if e['comparison_result'] in {'passed', 'failed'}
                 and not e['condition_ref'].startswith('semantic-')]
    assert any(e['condition_type'] == kind for e in automatic)
    for old in automatic:
        linked = [e for e in result['semantic_analysis'] if e.get('legacy_condition_ref') == old['condition_ref']]
        assert linked
        atom = linked[0]
        original = case[atom['source_field']]
        assert atom['source_span'] is not None
        assert original[slice(*atom['source_span'])] == atom['source_text']
        assert atom['comparison_result'] == old['comparison_result']


def test_actual_existing_comparison_reuse_is_not_counted_as_new():
    result = analyze(CASES['WLF00000025'])
    atoms = [e for e in result['semantic_analysis'] if e.get('validation') == 'registered_target_clause']
    assert len(atoms) == 3
    assert all(e['comparison_origin'] == 'legacy_reuse' for e in atoms)


def test_actual_standalone_registration_result_can_be_reused_without_inheriting_component_scope():
    result = analyze(CASES['WLF00003189'], disability='NO')
    registration = next(e for e in result['semantic_analysis'] if e.get('validation') == 'registered_target_clause'
                        and e.get('unit') == 'disability_status')
    assert registration['comparison_origin'] == 'legacy_reuse'
    assert registration['scope'] == 'program'
    assert registration['role_subject_scope_verified']
    assert registration['legacy_comparison_sources'][0]['source_field'] == 'selection_criteria'
    source = registration['legacy_comparison_sources'][0]
    assert CASES['WLF00003189']['selection_criteria'][slice(*source['source_span'])] == source['source_text']


def test_unknown_registration_does_not_infer_a_mismatch():
    result = analyze(CASES['WLF00001165'], disability='UNKNOWN')
    assert result['recommendation_decision'] != 'excluded'
    registration = next(e for e in result['semantic_analysis'] if e.get('unit') == 'disability_status')
    assert registration['comparison_result'] == 'unknown'
    assert not registration['decision_usable']


def test_actual_unresolved_employment_exception_does_not_become_candidate_from_registration_match():
    result = analyze(CASES['WLF00000025'], disability='YES', employment='EMPLOYED')
    assert result['recommendation_decision'] == 'unverified'
    employment = next(e for e in result['semantic_analysis'] if e.get('unit') == 'employment_status')
    assert employment['comparison_result'] == 'failed'
    assert not employment['decision_usable']


@pytest.mark.parametrize('sid', ['WLF00003189', 'WLF00001165', 'WLF00000025'])
def test_actual_parallel_path_does_not_change_policy_b_or_score(sid, monkeypatch):
    result = analyze(CASES[sid])
    monkeypatch.setattr(Semantic, 'evaluate', classmethod(lambda cls, *args, **kwargs: []))
    baseline = analyze(CASES[sid])
    for key in ('status', 'gap_conditions', 'review_conditions', 'match_score', 'evaluated_conditions',
                'passed_conditions', 'recommendation_status', 'recommendation_reason',
                'recommendation_uncertainty', 'confirmed_conditions', 'notes'):
        assert result[key] == baseline[key]


@pytest.mark.parametrize('original', ['등록장애인\n등록장애인', '다른 조건입니다.'])
def test_synthetic_ambiguous_or_missing_source_never_gets_a_fabricated_span(original):
    service = WelfareService(serv_id='test', target_details=original, selection_criteria='')
    row = Condition(**Parser.structure_service('등록장애인', '')[0])
    output = Semantic.evaluate(Matcher(), service, User(age=25, employment_status='OTHER'),
        {}, conditions=[row], observations={id(row): 'failed'})
    anchor = next(e for e in output if e.get('legacy_condition_ref') == 'condition-1')
    assert anchor['source_span'] is None
    assert anchor['comparison_origin'] == 'legacy_unlinked'
    assert not anchor['decision_usable']


def test_synthetic_support_content_is_independent_but_mixed_qualification_is_not():
    case = dict(CASES['WLF00003189'], selection_criteria='지원 내용: 월 10만원을 지원합니다.')
    assert analyze(case)['recommendation_decision'] == 'candidate'
    case['selection_criteria'] += ' 다만 등록하지 않은 사람도 지원합니다.'
    assert analyze(case, disability='NO')['recommendation_decision'] == 'unverified'


def test_synthetic_a_different_age_gate_in_a_footnote_is_not_neutral_prose():
    case = dict(CASES['WLF00003189'], selection_criteria='', target_details=
        '18세 이상 등록장애인을 대상으로 합니다.* 65세 이상인 청년을 지원합니다.')
    assert analyze(case)['recommendation_decision'] == 'unverified'


def test_reused_comparison_is_not_appended_a_second_time_to_decision_evidence():
    result = analyze(CASES['WLF00000025'])
    reused = {e['condition_ref'] for e in result['semantic_analysis']
              if e.get('validation') == 'registered_target_clause' and e.get('comparison_origin') == 'legacy_reuse'}
    assert reused
    assert not reused.intersection(e['condition_ref'] for e in result['decision_evidence'])


def test_synthetic_training_component_with_a_different_subject_is_not_certified_independent():
    case = dict(CASES['WLF00003189'])
    case['selection_criteria'] = case['selection_criteria'].replace("'직업적응훈련'", "'보호자훈련'")
    assert analyze(case, disability='NO')['recommendation_decision'] == 'unverified'
