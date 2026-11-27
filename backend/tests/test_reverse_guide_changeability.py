"""역설계 안내: 바꿀 수 없는 조건은 '바꾸면 충족'이라고 하지 않고, 대표 경로는 바꿀 수 있는 경로를 먼저 고른다."""
from types import SimpleNamespace as N

import pytest

from app.services import eligibility_path_service as paths
from app.services import structured_condition_service as base
from tests.test_condition_guides import condition, path_condition


def guide(c, current):
    return base.condition_guide(c, current, base.matches(c, current))["condition_guide"]


@pytest.mark.parametrize("c,current", [
    (condition("성별", "one_of", values=["여성"]), "남성"),
    (condition("국적", "one_of", values=["대한민국"]), "외국인"),
    (condition("등록 장애인", "is_true"), False),
    (condition("등록 장애인", "is_true", kind="exclusion"), True),
    (condition("중증 장애인", "is_true"), False),
    (condition("국가유공자·보훈대상자", "is_true"), False),
    (condition("북한이탈주민", "is_true"), False),
    (condition("자립준비청년", "is_true"), False),
    (condition("결혼이민자·다문화가족", "is_true"), False),
])
def test_target_group_conditions_are_informational_not_change_requests(c, current):
    text = guide(c, current)
    assert text and "대상입니다" in text or "제외됩니다" in text
    assert all(word not in text for word in ("변경되면", "바뀌면", "해당하게 되면", "바꿀 수 없", "신청할 수 있습니다"))
    # 대상자 조건은 '불가능'으로 단정하지 않는다(경로 순위에도 쓰지 않는다).
    assert not base.impossible_failure(c, current)


@pytest.mark.parametrize("c,current", [
    (condition("만 나이", "lte", 34, unit="세"), 35),
    (condition("혼인 기간", "lte", 7, unit="년"), 8),
    (condition("막내 자녀 나이", "lte", 6, unit="세"), 7),
])
def test_values_that_only_grow_cannot_come_back_under_an_upper_limit(c, current):
    text = guide(c, current)
    assert "충족할 수 없습니다" in text and "낮아" not in text
    assert base.impossible_failure(c, current)


def test_values_that_only_grow_can_reach_a_lower_limit():
    text = guide(condition("혼인 기간", "gte", 1, unit="년"), 0)
    assert "시간이 지나" in text and "충족합니다" in text
    assert not base.impossible_failure(condition("혼인 기간", "gte", 1, unit="년"), 0)


@pytest.mark.parametrize("c,current,expected", [
    (condition("고용 상태", "one_of", values=["미취업"]), "재직", "고용 상태가 미취업으로 바뀌면"),
    (condition("학교 구분", "one_of", values=["대학"]), "고등학교", "학교 구분이 대학으로 바뀌면"),
    (condition("주거 형태", "one_of", values=["월세"]), "자가", "주거 형태가 월세로 바뀌면"),
    (condition("만 나이", "gte", 18, unit="세"), 17, "나이가 만 18세 이상이 되면"),
    (condition("본인 월소득", "lte", 2_699_999, unit="원"), 3_000_000, "270만원 미만이 되면"),
    (condition("가구 소득인정액", "gte", 40.1, unit="%"), 30, "기준 중위소득 40% 초과가 되면"),
])
def test_changeable_conditions_use_correct_particles_and_source_wording(c, current, expected):
    assert expected in guide(c, current)


def test_long_region_list_is_shortened_in_guides():
    regions = [f"경기도 {name}시" for name in ("수원", "성남", "용인", "부천", "안산", "안양", "남양주")]
    text = guide(condition("거주지", "one_of", values=regions), "서울특별시")
    assert "경기도 수원시·경기도 성남시 등 7곳 중 한 곳으로 바뀌면" in text
    assert "경기도 남양주시" not in text


def _record(service, *specs):
    return N(source_sha256=base.source_hash(service), drafted_by="claude", preferences=[], paths=[
        N(path_key=key, label=key, kind="유형", priority=None, checks=[], conditions=[path_condition(c) for c in conds])
        for key, conds in specs])


SERVICE = N(serv_id="s", serv_name="합성", detail_url="", target_details="합성 원문", selection_criteria=None)


def test_recommended_path_has_the_lowest_published_difficulty_score():
    record = _record(SERVICE,
        ("여성", [condition("성별", "one_of", values=["여성"])]),
        ("저소득", [condition("본인 월소득", "lte", 2_000_000, unit="원")]),
        ("미취업", [condition("고용 상태", "one_of", values=["미취업"]), condition("본인 월소득", "lte", 1_000_000, unit="원")]))
    user = N(age=25, region=None, income_level=3_000_000, employment_status="EMPLOYED")
    result = paths.analyze(SERVICE, user, {"gender": "MALE"}, record)
    by_id = {p["path_id"]: p for p in result["eligibility_paths"]}
    # 성별 20점, 소득 50% 초과 2+5=7점, 고용 4점 + 소득 200% 초과 2+6=8점 = 12점
    assert {k: v["difficulty"] for k, v in by_id.items()} == {"여성": 20.0, "저소득": 7.0, "미취업": 12.0}
    assert [by_id[k]["rank"] for k in ("저소득", "미취업", "여성")] == [0, 1, 2]
    assert result["matched_path_id"] == "저소득"
    rows = {r["condition_type"]: r for p in result["eligibility_paths"] for r in p["conditions"]}
    assert rows["성별"]["impossible"] is False and rows["성별"]["difficulty"] == 20.0


def test_numeric_only_ties_are_ordered_by_gap_ratio():
    record = _record(SERVICE,
        ("소득40", [condition("본인 월소득", "lte", 2_000_000, unit="원")]),
        ("소득10", [condition("본인 월소득", "lte", 2_727_273, unit="원")]))
    user = N(age=25, region=None, income_level=3_000_000, employment_status=None)
    ranks = {p["path_id"]: p["rank"] for p in paths.analyze(SERVICE, user, {}, record)["eligibility_paths"]}
    assert ranks["소득10"] < ranks["소득40"]


def test_paths_that_can_never_be_met_go_last_even_with_fewer_failures():
    record = _record(SERVICE,
        ("청년", [condition("만 나이", "lte", 34, unit="세")]),
        ("일반", [condition("본인 월소득", "lte", 2_000_000, unit="원"), condition("고용 상태", "one_of", values=["미취업"])]))
    user = N(age=36, region=None, income_level=3_000_000, employment_status="EMPLOYED")
    result = paths.analyze(SERVICE, user, {}, record)
    by_id = {p["path_id"]: p for p in result["eligibility_paths"]}
    assert by_id["청년"]["impossible"] is True and by_id["일반"]["impossible"] is False
    assert by_id["일반"]["rank"] < by_id["청년"]["rank"]
    assert result["matched_path_id"] == "일반"
