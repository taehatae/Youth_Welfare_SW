"""간편 정책 찾기(비로그인 버튼형) 입력·응답 형식.

입력하지 않은 항목은 null(또는 생략)이며, 서버는 기본값을 채우지 않는다. 엔진이 미입력으로 보고 '확인 필요'로 남긴다.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.welfare import MatchedPoliciesResponse

YesNo = Literal["YES", "NO"]
# 금액 상한: 1조원. 화면은 만원 단위로 받아 원으로 바꿔 보낸다.
Won = Field(default=None, ge=0, le=1_000_000_000_000)


class QuickAnswers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 레거시 분석기가 나이 없이 동작하지 않아 유일한 필수 항목이다(기존 진단과 같은 범위).
    age: int = Field(..., ge=19, le=34)
    region: str | None = Field(default=None, min_length=1, max_length=100)
    income_monthly_won: int | None = Won
    # 기존 진단 화면의 고용 상태 선택지와 같다.
    employment: Literal["EMPLOYED", "EMPLOYED_SME", "PART_TIME", "UNEMPLOYED", "SELF_EMPLOYED",
                        "FREELANCER", "OTHER"] | None = None
    gender: Literal["MALE", "FEMALE"] | None = None
    household_size: int | None = Field(default=None, ge=1, le=20)
    household_monthly_income_won: int | None = Won
    recognized_household_income_won: int | None = Won
    asset_amount_won: int | None = Won
    household_debt_won: int | None = Won
    personal_asset_amount_won: int | None = Won
    personal_debt_won: int | None = Won
    car_value_won: int | None = Won
    housing_type: Literal["OWNED", "JEONSE", "MONTHLY", "FREE", "OTHER"] | None = None
    owns_home: YesNo | None = None
    household_homeless: YesNo | None = None
    disability_status: YesNo | None = None
    severe_disability: YesNo | None = None
    student_status: YesNo | None = None
    school_level: Literal["HIGH", "COLLEGE", "GRADUATE"] | None = None
    marital_status: Literal["SINGLE", "MARRIED", "DIVORCED", "WIDOWED"] | None = None
    marriage_years: int | None = Field(default=None, ge=0, le=80)
    spouse_monthly_income_won: int | None = Won
    children_count: int | None = Field(default=None, ge=0, le=20)
    youngest_child_age: int | None = Field(default=None, ge=0, le=40)
    pregnancy: YesNo | None = None
    nationality: Literal["KOREAN", "FOREIGN"] | None = None
    # null은 미응답, []는 '해당 없음'을 고른 경우다. 둘을 같게 다루지 않는다.
    special_targets: list[Literal["VETERAN", "NK_DEFECTOR", "MULTICULTURAL", "FARMER"]] | None = Field(
        default=None, max_length=4)
    basic_benefit_status: YesNo | None = None
    basic_benefit_types: list[Literal["LIVELIHOOD", "MEDICAL", "HOUSING", "EDUCATION"]] | None = Field(
        default=None, min_length=1, max_length=4)
    household_basic_benefit_status: YesNo | None = None
    near_poverty_status: YesNo | None = None
    single_parent_support_status: YesNo | None = None
    job_seek_registration: YesNo | None = None
    child_welfare_protection_experience: YesNo | None = None
    protection_ended: YesNo | None = None
    credit_bureau: Literal["KCB", "NICE"] | None = None
    credit_score: int | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode="after")
    def consistent(self):
        # 기존 진단 화면이 함께 받지 않는 조합은 거절한다. 엔진에 모순된 값을 넘기지 않는다.
        rules = [
            (self.school_level is not None and self.student_status != "YES", "학교 구분은 재학 중일 때만 입력할 수 있어요."),
            (self.severe_disability is not None and self.disability_status != "YES",
             "중증 여부는 등록 장애인일 때만 입력할 수 있어요."),
            (self.youngest_child_age is not None and not self.children_count,
             "막내 자녀 나이는 자녀가 있을 때만 입력할 수 있어요."),
            ((self.marriage_years is not None or self.spouse_monthly_income_won is not None)
             and self.marital_status != "MARRIED", "혼인 기간·배우자 소득은 기혼일 때만 입력할 수 있어요."),
            ((self.credit_score is None) != (self.credit_bureau is None), "신용점수는 평가사와 함께 입력해주세요."),
            (self.basic_benefit_types is not None and self.basic_benefit_status != "YES",
             "급여 종류는 기초생활보장 수급자일 때만 입력할 수 있어요."),
            (self.protection_ended is not None and self.child_welfare_protection_experience != "YES",
             "보호 종료 여부는 보호 경험이 있을 때만 입력할 수 있어요."),
            (self.housing_type == "OWNED" and self.owns_home == "NO", "자가 거주와 주택 미보유는 함께 고를 수 없어요."),
            (self.special_targets is not None and len(set(self.special_targets)) != len(self.special_targets),
             "같은 대상을 두 번 고를 수 없어요."),
            (self.basic_benefit_types is not None and len(set(self.basic_benefit_types)) != len(self.basic_benefit_types),
             "같은 급여를 두 번 고를 수 없어요."),
        ]
        for broken, message in rules:
            if broken:
                raise ValueError(message)
        return self


class QuickEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(..., min_length=1, max_length=30)
    answers: QuickAnswers


class QuickCategory(BaseModel):
    id: str
    label: str
    policy_count: int


class QuickField(BaseModel):
    field: str
    policy_count: int
    questions: list[str]


class QuickCategoryDetail(QuickCategory):
    # 자격 경로가 있어 비교 조건을 알 수 있는 정책 수
    path_policy_count: int
    questions: list[str]
    # 질문마다 그 답을 비교에 쓰는 정책 수(화면 안내용)
    question_policy_counts: dict[str, int]
    fields: list[QuickField]
    # 입력으로 비교할 수 없어 '확인 필요'로만 안내하는 조건 항목
    unsupported_fields: list[str]
    check_count: int


class QuickCategoriesResponse(BaseModel):
    categories: list[QuickCategory]


class QuickEvaluateResponse(BaseModel):
    category: str
    category_label: str
    evaluated_at: str
    matched: MatchedPoliciesResponse
