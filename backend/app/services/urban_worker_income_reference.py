"""전년도 도시근로자 가구원수별 가구당 월평균소득(100%) 표.

공공임대주택(행복주택·매입임대·통합공공임대)과 공공분양이 소득 기준으로 쓴다. 공고마다 '전년도' 통계를 쓰므로
공고 연도(적용 연도)로 찾는다. 1~5인은 LH청약플러스·공공임대주택 포털 표가 일치하고, 6인은 2차 출처라
공고문과 대조가 필요하다. 7인 이상은 표에 넣지 않았다(None → 비교하지 않음).

https://apply.lh.or.kr/lhapply/cm/cntnts/cntntsView.do?cntntsId=1201391&mi=1201663
"""

MONTHLY_URBAN_WORKER_INCOME_WON: dict[int, dict[int, int]] = {
    # 2025년 통계, 2026년 공고에 적용
    2026: {1: 3_813_363, 2: 5_866_270, 3: 8_168_429, 4: 8_802_202, 5: 9_326_985, 6: 9_906_263},
}


def urban_worker_income_amount(year: int, household_size: int | None) -> int | None:
    if not household_size:
        return None
    table = MONTHLY_URBAN_WORKER_INCOME_WON.get(year) or MONTHLY_URBAN_WORKER_INCOME_WON[max(MONTHLY_URBAN_WORKER_INCOME_WON)]
    return table.get(int(household_size))
