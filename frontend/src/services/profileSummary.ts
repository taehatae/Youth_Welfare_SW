import {
  ASSETS,
  EMPLOYMENT,
  GENDER,
  HOUSING,
  INCOME,
  MARRIAGE,
  QUALIFICATIONS,
  YES_NO,
  EMPTY_DRAFT,
  EMPTY_ADDITIONAL_ELIGIBILITY,
  type ProfileDraft,
  type AdditionalEligibilityDraft,
  type Option,
} from "../data/profileOptions"
import { REGIONS } from "../data/regions"
import type { JsonValue, UserProfileInput } from "../types/welfareApi"

const label = (options: Option[], value: unknown) =>
  options.find(([code]) => code === value)?.[1] ?? "미확인"
const count = (value: number | null, unit = "명") =>
  value == null ? "미확인" : `${value}${unit}`
const extraFields = [
  ["basicBenefitStatus", "basic_benefit_status", "기초생활급여 수급", "status"],
  ["basicBenefitTypes", "basic_benefit_types", "급여 종류", "benefits"],
  ["nearPovertyStatus", "near_poverty_status", "차상위계층", "status"],
  [
    "singleParentSupportStatus",
    "single_parent_support_status",
    "한부모가족 지원 대상",
    "status",
  ],
  [
    "householdMonthlyIncomeWon",
    "household_monthly_income_won",
    "가구 월소득",
    "money",
  ],
  [
    "householdIncomeRecognitionKnown",
    "household_income_recognition_known",
    "소득인정액 확인 여부",
    "status",
  ],
  [
    "recognizedHouseholdIncomeWon",
    "recognized_household_income_won",
    "가구 소득인정액",
    "money",
  ],
  [
    "householdBasicBenefitStatus",
    "household_basic_benefit_status",
    "가구 내 급여 수급자",
    "status",
  ],
  [
    "childWelfareProtectionExperience",
    "child_welfare_protection_experience",
    "보호 경험",
    "status",
  ],
  ["protectionEnded", "protection_ended", "보호 종료", "status"],
  ["protectionEndMonth", "protection_end_month", "보호 종료 연월", "text"],
  [
    "protectionDurationMonths",
    "protection_duration_months",
    "보호 기간",
    "months",
  ],
  ["jobSeekRegistration", "job_seek_registration", "구직 등록", "status"],
  [
    "employmentSupportProgram",
    "employment_support_program",
    "취업지원 프로그램",
    "status",
  ],
  [
    "selfSufficiencyProgramStatus",
    "self_sufficiency_program_status",
    "자활사업 참여",
    "status",
  ],
  [
    "registeredAddressSido",
    "registered_address_sido",
    "주민등록상 시도",
    "text",
  ],
  [
    "registeredAddressDistrict",
    "registered_address_district",
    "주민등록상 시군구",
    "text",
  ],
  [
    "registeredResidenceStartMonth",
    "registered_residence_start_month",
    "주민등록 거주 시작",
    "text",
  ],
] as const
const benefits: Record<string, string> = {
  LIVELIHOOD: "생계",
  MEDICAL: "의료",
  HOUSING: "주거",
  EDUCATION: "교육",
  NONE: "해당 없음",
}
function extraLabel(value: JsonValue | undefined, kind: string) {
  if (value == null || value === "") return "미입력"
  if (kind === "status") return label(YES_NO, value)
  if (kind === "money")
    return typeof value === "number"
      ? `${value.toLocaleString("ko-KR")}원`
      : "미확인"
  if (kind === "months") return `${value}개월`
  if (kind === "benefits")
    return Array.isArray(value)
      ? value.map((v) => benefits[String(v)] ?? "미확인").join(", ") || "미입력"
      : "미확인"
  return String(value)
}
export function profileSummary(profile: UserProfileInput | null) {
  if (!profile) return []
  const p = profile.eligibility_conditions ?? {}
  const extra = p.additional_conditions ?? {}
  return [
    {
      title: "기본 정보",
      items: [
        ["나이", `만 ${profile.age}세`],
        ["성별", label(GENDER, p.gender)],
      ],
    },
    { title: "거주 지역", items: [["거주지", profile.region]] },
    {
      title: "소득",
      items: [
        ["본인 월소득", `${profile.income_level.toLocaleString("ko-KR")}원`],
        ["소득 종류", label(INCOME, p.income_type)],
      ],
    },
    {
      title: "가구 · 주거",
      items: [
        ["가구원", count(p.household_size)],
        ["주거 형태", label(HOUSING, p.housing_type)],
        [
          "주택 보유",
          p.owns_home == null ? "미확인" : p.owns_home ? "보유" : "미보유",
        ],
        ["재산", label(ASSETS, p.asset_range)],
      ],
    },
    {
      title: "고용",
      items: [
        [
          "고용 상태",
          label(
            EMPLOYMENT,
            extra.employment_detail ?? profile.employment_status,
          ),
        ],
      ],
    },
    {
      title: "추가 조건",
      items: [
        ["재학 여부", label(YES_NO, p.student_status)],
        ["장애 여부", label(YES_NO, p.disability_status)],
        ["혼인", label(MARRIAGE, p.marital_status)],
        ["자녀", count(p.children_count)],
        [
          "자격증",
          extra.qualification_status === "NO"
            ? "미보유"
            : (p.qualifications ?? []).length
              ? p.qualifications.map((v) => label(QUALIFICATIONS, v)).join(", ")
              : "미확인",
        ],
        ...extraFields.map(([, key, title, kind]) => [
          title,
          extraLabel(extra[key], kind),
        ]),
      ],
    },
  ]
}

// Open edits from the displayed snapshot, not an unrelated unfinished draft.
export function profileToDraft(profile: UserProfileInput): ProfileDraft {
  const p = profile.eligibility_conditions ?? {}
  const extra = p.additional_conditions ?? {}
  const region =
    Object.keys(REGIONS).find(
      (name) =>
        profile.region === name || profile.region.startsWith(name + " "),
    ) ?? ""
  const additional: AdditionalEligibilityDraft = {
    ...EMPTY_ADDITIONAL_ELIGIBILITY,
    basicBenefitTypes: [],
  }
  for (const [draftKey, key] of extraFields) {
    const value = extra[key]
    if (draftKey === "basicBenefitTypes")
      additional.basicBenefitTypes = Array.isArray(value)
        ? value.filter((v): v is string => typeof v === "string")
        : []
    else additional[draftKey] = value == null ? "" : String(value)
  }
  return {
    ...EMPTY_DRAFT,
    age: String(profile.age),
    region,
    district:
      region === "세종특별자치시"
        ? region
        : profile.region.slice(region.length).trim(),
    incomeMajor: String(Math.floor(profile.income_level / 1_000_000)),
    incomeMinor: String((profile.income_level % 1_000_000) / 10_000),
    gender: p.gender ?? "UNKNOWN",
    incomeType: p.income_type ?? "UNKNOWN",
    housing: p.housing_type ?? "",
    ownsHome: p.owns_home == null ? "UNKNOWN" : p.owns_home ? "YES" : "NO",
    householdSize: p.household_size == null ? "" : String(p.household_size),
    asset: p.asset_range ?? "",
    employment:
      typeof extra.employment_detail === "string"
        ? extra.employment_detail
        : profile.employment_status,
    disability: p.disability_status ?? "UNKNOWN",
    student: p.student_status ?? "UNKNOWN",
    maritalStatus: p.marital_status ?? "UNKNOWN",
    childrenCount: p.children_count == null ? "" : String(p.children_count),
    qualificationStatus:
      typeof extra.qualification_status === "string"
        ? extra.qualification_status
        : (p.qualifications ?? []).length
          ? "YES"
          : "UNKNOWN",
    qualifications: [...(p.qualifications ?? [])],
    additionalEligibility: additional,
  }
}

export function conditionStep(field: string): number {
  if (field === "age") return 0
  if (field === "region") return 1
  if (["income_amount", "income_level"].includes(field)) return 2
  if (["employment", "employment_status"].includes(field)) return 4
  return 5
}
