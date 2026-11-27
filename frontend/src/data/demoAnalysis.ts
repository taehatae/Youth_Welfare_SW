import type { UserProfileInput, WelfareAnalysis } from "../types/welfareApi"

// Fictional presentation scenario. Keep it clearly separated from live API data.

export const DEMO_PROFILE: UserProfileInput = {
  age: 27,

  region: "서울특별시 관악구",

  income_level: 2_100_000,

  employment_status: "UNEMPLOYED",

  eligibility_conditions: {
    gender: "UNKNOWN",

    household_size: 1,

    income_type: "UNKNOWN",

    asset_range: "100M_200M",

    housing_type: "MONTHLY",

    owns_home: false,

    disability_status: "UNKNOWN",

    student_status: "NO",

    marital_status: "SINGLE",

    children_count: 0,

    qualifications: [],

    additional_conditions: {},
  },
}

export const DEMO_ANALYSIS: WelfareAnalysis = {
  userId: "demo-user-001",

  matched: {
    matched_count: 2,

    policies: [
      {
        policy_id: "DEMO-001",

        title: "청년 월세 지원 (시연용)",

        category: "주거",

        support_amount: "월 최대 20만원 · 예시",

        match_score: 85,

        application_start_date: "2026-10-01",

        application_end_date: "2026-12-31",
      },

      {
        policy_id: "DEMO-002",

        title: "국민취업지원제도 (시연용)",

        category: "취업",

        support_amount: "구직 지원 · 예시",

        match_score: 78,

        application_start_date: "2026-09-01",

        application_end_date: "2026-10-15",
      },
    ],
  },

  reverse: {
    recommendations: [
      {
        target_policy: "중소기업 재직 청년 지원 (시연용)",

        current_eligibility: false,

        missing_conditions: [
          {
            field: "employment_status",

            current_value: "구직 중",

            required_value: "중소기업 재직",

            action_guide:
              "중소기업 취업 후 신청 요건과 모집 여부를 확인하는 상황을 가정한 예시입니다.",
          },
        ],
      },
    ],
  },
}
