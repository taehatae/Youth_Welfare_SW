"""Official monthly Korean median-household-income reference amounts.

Source: Ministry of Health and Welfare, "기준 중위소득", annual table.
https://www.mohw.go.kr/menu.es?mid=a10708010900
The table lists household sizes 1 through 7 for years 2021 through 2027.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re


CURRENT_APPLICABLE_YEAR = date.today().year
SOURCE_URL = "https://www.mohw.go.kr/menu.es?mid=a10708010900"

MONTHLY_MEDIAN_INCOME_WON: dict[int, dict[int, int]] = {
    2021: {
        1: 1_827_831,
        2: 3_088_079,
        3: 3_983_950,
        4: 4_876_290,
        5: 5_757_373,
        6: 6_628_603,
        7: 7_497_198,
    },
    2022: {
        1: 1_944_812,
        2: 3_260_085,
        3: 4_194_701,
        4: 5_121_080,
        5: 6_024_515,
        6: 6_907_004,
        7: 7_780_592,
    },
    2023: {
        1: 2_077_892,
        2: 3_456_155,
        3: 4_434_816,
        4: 5_400_964,
        5: 6_330_688,
        6: 7_227_981,
        7: 8_107_515,
    },
    2024: {
        1: 2_228_445,
        2: 3_682_609,
        3: 4_714_657,
        4: 5_729_913,
        5: 6_695_735,
        6: 7_618_369,
        7: 8_514_994,
    },
    2025: {
        1: 2_392_013,
        2: 3_932_658,
        3: 5_025_353,
        4: 6_097_773,
        5: 7_108_192,
        6: 8_064_805,
        7: 8_988_428,
    },
    2026: {
        1: 2_564_238,
        2: 4_199_292,
        3: 5_359_036,
        4: 6_494_738,
        5: 7_556_719,
        6: 8_555_952,
        7: 9_515_150,
    },
    2027: {
        1: 2_736_042,
        2: 4_480_645,
        3: 5_718_091,
        4: 6_929_885,
        5: 8_063_019,
        6: 9_129_201,
        7: 10_152_665,
    },
}


def median_income_amount(year: int, household_size: int) -> int | None:
    """Return the published monthly amount; unsupported inputs are unknown."""

    return MONTHLY_MEDIAN_INCOME_WON.get(year, {}).get(household_size)


def median_income_threshold(
    year: int,
    household_size: int,
    percentage: Decimal,
) -> int | None:
    """Return the percentage threshold rounded to the nearest whole won."""

    median_amount = median_income_amount(year, household_size)
    if median_amount is None or percentage < 0:
        return None

    amount = Decimal(median_amount) * percentage / Decimal(100)
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def resolve_policy_reference_year(
    source_text: str,
    service_reference_year: str | None,
) -> int | None:
    """Resolve only an explicit source year or the service's criterion year.

    A conflicting explicit year and service metadata is ambiguous and returns
    None. The current application year is intentionally not a silent fallback.
    """

    explicit_years = {
        int(match)
        for match in re.findall(r"(?<!\d)(20\d{2})년(?=\s*(?:기준\s*)?중위소득)", source_text)
    }
    if len(explicit_years) > 1:
        return None

    metadata_year = None
    if isinstance(service_reference_year, str):
        match = re.fullmatch(r"\s*(20\d{2})년?\s*", service_reference_year)
        if match:
            metadata_year = int(match.group(1))

    explicit_year = next(iter(explicit_years), None)
    current_year_reference = bool(
        re.search(r"당해년도|당해 연도|올해", source_text)
    )
    if current_year_reference:
        if metadata_year is not None and metadata_year != CURRENT_APPLICABLE_YEAR:
            return None
        return CURRENT_APPLICABLE_YEAR

    if explicit_year is not None and metadata_year is not None:
        return explicit_year if explicit_year == metadata_year else None
    return explicit_year if explicit_year is not None else metadata_year
