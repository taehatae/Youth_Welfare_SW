from scripts.lint_draft import lint_policy


def policy(common=(), common_checks=(), paths=()):
    return {"common": list(common), "common_checks": list(common_checks), "paths": list(paths)}


def rules(p):
    return {(key, rule) for key, rule, _ in lint_policy(p)}


def test_comparable_criterion_left_in_checks_is_flagged():
    # 채점 지적: "중소기업 1년 이하 재직" → 중소기업은 조건, 1년은 확인 사항
    p = policy(paths=[{"id": "청년", "conditions": [], "checks": ["중소기업 1년 이하 재직자일 것"]}])
    assert ("청년|k0", "R1") in rules(p)
    p["paths"][0]["conditions"] = [{"field": "고용 상태", "op": "one_of", "values": ["중소기업 재직"]}]
    assert rules(p) == set()


def test_generic_check_and_out_of_scope_age_path_are_flagged():
    p = policy(common_checks=["자산 기준은 공고문 확인"],
               paths=[{"id": "노인", "conditions": [{"field": "만 나이", "op": "gte", "value": 65}], "checks": []}])
    assert rules(p) == {("_common|k0", "R3"), ("노인|c0", "R4")}


def test_asset_criterion_missing_from_one_of_many_paths_is_flagged():
    car = {"field": "자동차가액", "op": "lte", "value": 37_080_000}
    p = policy(paths=[{"id": i, "conditions": [car] if i != "C" else [], "checks": []} for i in "ABC"])
    assert ("C|c", "R5") in rules(p)
