"""Synthetic bounded clauses; public excerpts are explicitly labelled below."""
import pytest

from app.models.user import User
from app.models.welfare_service import WelfareService
from app.services.semantic_condition_service import SemanticConditionService as Semantic
from app.services.eligibility_matching_service import EligibilityMatchingService as Matcher


TEXT = "만 18세 이상 34세 이하의 미취업 청년 중 기준 중위소득 100% 이하인 자"


def test_synthetic_extraction_is_separate_from_income_comparability():
    group = Semantic.decompose(TEXT)[0]
    assert group.relation == "AND"
    assert [a.condition_type for a in group.atoms] == ["age", "employment", "income_ratio"]
    assert group.atoms[0].value_number == 18
    assert group.atoms[0].upper_value_number == 34
    assert group.atoms[2].subject == "unresolved"
    assert "INCOME_METRIC_UNRESOLVED" in group.atoms[2].reason_codes
    for atom in group.atoms:
        assert TEXT[slice(*atom.source_span)] == atom.source_text


def analyze(text, age=25, employment="UNEMPLOYED", selection=""):
    from app.models.welfare_eligibility_condition import WelfareEligibilityCondition
    from app.services.eligibility_condition_service import EligibilityConditionService
    service = WelfareService(serv_id="synthetic", serv_name="Test", target_details=text,
                             selection_criteria=selection, detail_url="")
    rows = [WelfareEligibilityCondition(serv_id="synthetic", **row)
            for row in EligibilityConditionService.structure_service(text, selection)]
    return Matcher().analyze_service(User(age=age, region="서울", income_level=0,
        employment_status=employment), service, rows, {})


@pytest.mark.parametrize("age,employment,decision", [
    (25, "UNEMPLOYED", "candidate"), (35, "UNEMPLOYED", "excluded"),
    (25, "EMPLOYED", "excluded"), (25, "OTHER", "candidate"),
])
def test_synthetic_clear_and_uses_partial_input_without_overriding_policy_b(age, employment, decision):
    result = analyze(TEXT, age, employment)
    assert result["recommendation_decision"] == decision
    assert result["status"] == "needs_review"
    assert result["semantic_analysis"]
    assert any(e["condition_ref"].startswith("semantic-") for e in result["decision_evidence"])


@pytest.mark.parametrize("text", [
    "만 18세 이상 34세 이하의 미취업 청년 또는 재학생",
    TEXT + ". 다만 예외적으로 재직자도 참여 가능",
    "자녀가 " + TEXT,
    "우대 조건: " + TEXT,
    "세부 의료비 지원: " + TEXT,
    "졸업 당시 " + TEXT,
    TEXT + "이며 별도 인정 대상",
])
def test_synthetic_ambiguous_context_is_not_certified(text):
    result = analyze(text, age=40)
    assert result["recommendation_decision"] == "unverified"


def test_synthetic_cross_field_exception_blocks_semantic_gate():
    assert analyze(TEXT, age=40, selection="다만 예외 대상은 별도 심사")['recommendation_decision'] == "unverified"


def test_synthetic_refs_are_stable_and_no_input_values_are_copied():
    first = analyze(TEXT)
    second = analyze(TEXT, age=26)
    assert [e['condition_ref'] for e in first['semantic_analysis']] == [e['condition_ref'] for e in second['semantic_analysis']]
    assert all('current_value' not in e for e in first['semantic_analysis'])


@pytest.mark.parametrize('age,expected', [(17, 'excluded'), (18, 'candidate'), (34, 'candidate'), (35, 'excluded')])
def test_synthetic_and_age_boundaries(age, expected):
    assert analyze(TEXT, age=age)['recommendation_decision'] == expected


def test_synthetic_unsupported_income_is_not_personal_zero_income():
    result = analyze(TEXT, employment='EMPLOYED')
    income = next(e for e in result['semantic_analysis'] if e.get('condition_type') == 'income_ratio')
    assert income['comparison_result'] == 'unknown'
    assert not income['decision_usable']
    evidence = next(e for e in result['decision_evidence']
                    if e['condition_ref'] == income['condition_ref'])
    assert not evidence['semantics_verified']
    assert evidence['input_fields'] == []
    assert result['recommendation_decision'] == 'excluded'  # confirmed AND employment failure


@pytest.mark.parametrize('text', [
    '만 18세 이상 34세 이하의 미취업 청년을 지원합니다.',
    '만 18세 이상 34세 이하의 청년 중 기준 중위소득 100% 이하인 자',
])
def test_synthetic_two_atom_and_forms(text):
    group = Semantic.decompose(text)[0]
    assert group.relation == 'AND'
    assert len(group.atoms) == 2
    assert analyze(text)['recommendation_decision'] == 'candidate'


def test_synthetic_income_recognition_reuses_existing_comparator():
    from app.services.median_income_reference import median_income_threshold
    text = '만 18세 이상의 청년 중 가구 소득인정액이 기준 중위소득 100% 이하인 자'
    service = WelfareService(serv_id='income', serv_name='Test', target_details=text,
        selection_criteria='', reference_year='2025', detail_url='')
    user = User(age=25, region='서울', income_level=0, employment_status='OTHER')
    limit = int(median_income_threshold(year=2025, household_size=1, percentage=100))
    for amount, expected in [(limit, 'passed'), (limit + 1, 'failed')]:
        rows = Semantic.evaluate(Matcher(), service, user, {'household_size': 1,
            'additional_conditions': {'recognized_household_income_won': amount}})
        assert next(e for e in rows if e.get('condition_type') == 'income_ratio')['comparison_result'] == expected


def test_public_excerpts_preserve_unresolved_atoms_and_source_links():
    import json
    from pathlib import Path
    cases = json.loads((Path(__file__).parent / 'fixtures' / 'eligibility_policy_excerpts.json').read_text(encoding='utf-8'))['policies']
    for case in cases:
        clauses = Semantic.decompose(case['target_details'])
        assert clauses
        assert all(c.atoms for c in clauses)
        for clause in clauses:
            for atom in clause.atoms:
                assert case['target_details'][slice(*atom.source_span)] == atom.source_text
                assert not atom.validation == 'bounded_full_clause'
        if case['serv_id'] == 'WLF00001149':
            assert clauses[0].relation == 'OR'
            assert not any(a.value_text == 'UNEMPLOYED' and not a.reason_codes
                           for c in clauses for a in c.atoms)


def test_synthetic_unicode_multiline_offsets_and_unresolved_suffix():
    text = '\n  ' + TEXT + '\n다만 별도 심사\n'
    clauses = Semantic.decompose(text)
    for clause in clauses:
        assert text[slice(*clause.source_span)] == clause.source_text
        for atom in clause.atoms:
            assert text[slice(*atom.source_span)] == atom.source_text
    assert analyze(text, age=40)['recommendation_decision'] == 'unverified'


def test_synthetic_separate_target_groups_are_not_implicitly_and():
    text = ('만 18세 이상 24세 이하의 미취업 청년인 자\n'
            '만 25세 이상 34세 이하의 미취업 청년인 자')
    result = analyze(text, age=27)
    assert result['recommendation_decision'] == 'unverified'
    assert not any(e['decision_usable'] for e in result['semantic_analysis'])


def test_synthetic_selection_only_keeps_conditions_and_spans_without_certifying_scope():
    text = TEXT + '\n다만 예외 적용 대상은 별도 심사'
    result = analyze('', selection=text)
    assert result['recommendation_decision'] == 'unverified'
    assert result['semantic_analysis']
    for item in result['semantic_analysis']:
        assert item['source_field'] == 'selection_criteria'
        assert text[slice(*item['source_span'])] == item['source_text']
        assert not item['decision_usable']


def test_synthetic_parallel_evaluation_preserves_all_legacy_analysis_fields(monkeypatch):
    result = analyze(TEXT)
    monkeypatch.setattr(Semantic, 'augment', staticmethod(lambda decision, semantic: decision))
    baseline = analyze(TEXT)
    for field in ('status', 'match_score', 'evaluated_conditions', 'passed_conditions',
                  'gap_conditions', 'review_conditions', 'recommendation_status',
                  'recommendation_reason', 'recommendation_uncertainty', 'confirmed_conditions', 'notes'):
        assert result[field] == baseline[field]
    assert result['recommendation_decision'] == 'candidate'
    assert baseline['recommendation_decision'] == 'unverified'


@pytest.mark.parametrize('text', [
    '만 18세 이상 34세 이하의 정기소득이 없는 청년인 자',
    '보호자의 서울 거주와 자녀의 재학 조건을 충족한 자',
    '다른 대출상품: ' + TEXT,
    '만 19세 미만은 참여가 불가합니다.',
    '등록장애인 또는 의사의 소견으로 인정된 사람을 지원합니다.',
])
def test_synthetic_unsupported_semantics_are_not_newly_certified(text):
    result = analyze(text)
    assert not any(e['decision_usable'] and e.get('validation') == 'bounded_full_clause'
                   for e in result['semantic_analysis'])
