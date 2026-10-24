import type { UserProfileInput } from "../types/welfareApi"

import { REGIONS } from "./regions"

export type Option = readonly [value: string, label: string]

export const GENDER: Option[] = [
  ["MALE", "남성"],
  ["FEMALE", "여성"],
  ["UNKNOWN", "선택 안 함"],
]

export const INCOME: Option[] = [
  ["LABOR", "근로소득"],
  ["BUSINESS", "사업소득"],
  ["FREELANCE", "프리랜서 소득"],
  ["NONE", "소득 없음"],
  ["UNKNOWN", "기타 / 주된 소득원 미확인"],
]

export const HOUSING: Option[] = [
  ["OWNED", "자가 거주"],
  ["JEONSE", "전세"],
  ["MONTHLY", "월세 (보증금 포함 여부 무관)"],
  ["FREE", "무상 거주"],
  ["OTHER", "기타"],
]

export const ASSETS: Option[] = [
  ["UNDER_100M", "1억원 미만"],
  ["100M_200M", "1억원 이상 2억원 미만"],
  ["200M_300M", "2억원 이상 3억원 미만"],
  ["300M_500M", "3억원 이상 5억원 미만"],
  ["OVER_500M", "5억원 이상"],
]

export const EMPLOYMENT: Option[] = [
  ["EMPLOYED", "재직 (대기업 / 공공기관 등)"],
  ["EMPLOYED_SME", "중소기업 재직"],
  ["PART_TIME", "아르바이트"],
  ["UNEMPLOYED", "무직 / 구직 중"],
  ["SELF_EMPLOYED", "자영업"],
  ["FREELANCER", "프리랜서"],
  ["OTHER", "기타"],
]

export const YES_NO: Option[] = [
  ["YES", "해당"],
  ["NO", "해당 없음"],
  ["UNKNOWN", "미확인"],
]

export const MARRIAGE: Option[] = [
  ["SINGLE", "미혼"],
  ["MARRIED", "기혼"],
  ["DIVORCED", "이혼"],
  ["WIDOWED", "사별"],
  ["UNKNOWN", "미확인"],
]

// 초기 선택 목록. 목록 밖 자격은 코드 OTHER로만 보존하고 자동 충족 판정에 쓰지 않는다.

export const QUALIFICATIONS: Option[] = [
  ["DRIVER_1", "1종 운전면허"],
  ["DRIVER_2", "2종 운전면허"],
  ["SOCIAL_WORKER_1", "사회복지사 1급"],
  ["SOCIAL_WORKER_2", "사회복지사 2급"],
  ["COMPUTER_1", "컴퓨터활용능력 1급"],
  ["COMPUTER_2", "컴퓨터활용능력 2급"],
  ["ENGINEER_INFORMATION", "정보처리기사"],
  ["OTHER", "목록에 없는 자격 보유"],
]

export const numberOptions = (
  start: number,
  end: number,
  unit = "",
): Option[] =>
  Array.from({ length: end - start + 1 }, (_, n) => [
    String(start + n),
    `${start + n}${unit}`,
  ])

export interface ProfileDraft {
  age: string
  region: string
  district: string
  incomeMajor: string
  incomeMinor: string

  gender: string
  incomeType: string
  housing: string
  ownsHome: string
  householdSize: string

  asset: string
  employment: string
  disability: string
  student: string
  maritalStatus: string

  childrenCount: string
  qualificationStatus: string
  qualifications: string[]
  additionalEligibility?: AdditionalEligibilityDraft
}

export interface AdditionalEligibilityDraft {
  basicBenefitStatus: string
  basicBenefitTypes: string[]
  nearPovertyStatus: string
  singleParentSupportStatus: string
  householdMonthlyIncomeWon: string
  householdIncomeRecognitionKnown: string
  recognizedHouseholdIncomeWon: string
  householdBasicBenefitStatus: string
  childWelfareProtectionExperience: string
  protectionEnded: string
  protectionEndMonth: string
  protectionDurationMonths: string
  jobSeekRegistration: string
  employmentSupportProgram: string
  selfSufficiencyProgramStatus: string
  registeredAddressSido: string
  registeredAddressDistrict: string
  registeredResidenceStartMonth: string
}

export const EMPTY_ADDITIONAL_ELIGIBILITY: AdditionalEligibilityDraft = {
  basicBenefitStatus: "",
  basicBenefitTypes: [],
  nearPovertyStatus: "",
  singleParentSupportStatus: "",
  householdMonthlyIncomeWon: "",
  householdIncomeRecognitionKnown: "",
  recognizedHouseholdIncomeWon: "",
  householdBasicBenefitStatus: "",
  childWelfareProtectionExperience: "",
  protectionEnded: "",
  protectionEndMonth: "",
  protectionDurationMonths: "",
  jobSeekRegistration: "",
  employmentSupportProgram: "",
  selfSufficiencyProgramStatus: "",
  registeredAddressSido: "",
  registeredAddressDistrict: "",
  registeredResidenceStartMonth: "",
}

export const EMPTY_DRAFT: ProfileDraft = {
  age: "",
  region: "",
  district: "",
  incomeMajor: "",
  incomeMinor: "",
  gender: "UNKNOWN",
  incomeType: "UNKNOWN",
  housing: "",
  ownsHome: "UNKNOWN",
  householdSize: "",
  asset: "",
  employment: "",
  disability: "UNKNOWN",
  student: "UNKNOWN",
  maritalStatus: "UNKNOWN",
  childrenCount: "",
  qualificationStatus: "UNKNOWN",
  qualifications: [],
}

export const incomeWon = (draft: ProfileDraft) =>
  (Number(draft.incomeMajor) * 100 + Number(draft.incomeMinor)) * 10000

export function stepError(d: ProfileDraft, step: number): string {
  if (step === 0 && !numberOptions(19, 34).some(([v]) => v === d.age))
    return "진단 대상인 만 19~34세 중 나이를 선택해주세요."

  if (step === 1 && !REGIONS[d.region]?.includes(d.district))
    return "시도와 해당 시군구를 모두 선택해주세요."

  if (
    step === 2 &&
    (!numberOptions(0, 99).some(([v]) => v === d.incomeMajor) ||
      !numberOptions(0, 99).some(([v]) => v === d.incomeMinor))
  )
    return "월 소득의 백만원 단위와 나머지 만원 단위를 모두 선택해주세요."

  if (step === 2 && d.incomeType === "NONE" && incomeWon(d) !== 0)
    return "소득 없음은 월 소득이 0원일 때 선택할 수 있어요."

  if (step === 3 && !HOUSING.some(([v]) => v === d.housing))
    return "현재 주거 형태를 선택해주세요."

  if (step === 3 && d.housing === "OWNED" && d.ownsHome === "NO")
    return "자가 거주와 주택 미보유가 함께 선택되어 있어요. 주택 보유 여부를 확인해주세요."

  if (step === 4 && !EMPLOYMENT.some(([v]) => v === d.employment))
    return "현재 고용 상태를 선택해주세요."

  if (step === 5 && d.qualificationStatus === "YES" && !d.qualifications.length)
    return "보유한 자격을 선택해주세요. 목록에 없으면 해당 항목을 선택할 수 있어요."

  if (step === 5 && d.additionalEligibility) {
    const additional = d.additionalEligibility
    const optionalAmounts = [
      additional.householdMonthlyIncomeWon,
      additional.recognizedHouseholdIncomeWon,
      additional.protectionDurationMonths,
    ]
    if (
      optionalAmounts.some(
        (value) => value !== "" && (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value))),
      )
    )
      return "추가 금액과 보호 기간은 0 이상의 정수로 입력해주세요."
    if (
      additional.protectionEndMonth &&
      !validYearMonth(additional.protectionEndMonth)
    )
      return "보호 종료 연월을 확인해주세요."
    if (
      additional.registeredResidenceStartMonth &&
      !validYearMonth(additional.registeredResidenceStartMonth)
    )
      return "주민등록상 거주 시작 연월을 확인해주세요."
  }

  return ""
}

function validYearMonth(value: string): boolean {
  const match = /^(\d{4})-(\d{2})$/.exec(value)
  return !!match && Number(match[1]) >= 1900 && Number(match[2]) >= 1 && Number(match[2]) <= 12
}

export function toProfile(d: ProfileDraft): UserProfileInput {
  if (!isDraft(d))
    throw new Error(
      "저장된 선택값을 확인할 수 없어요. 정보를 다시 선택해주세요.",
    )

  for (let step = 0; step < 6; step++) {
    const error = stepError(d, step)
    if (error) throw new Error(error)
  }

  const extra = {
    ...EMPTY_ADDITIONAL_ELIGIBILITY,
    ...d.additionalEligibility,
  }
  const optionalNumber = (value: string) => value === "" ? null : Number(value)

  return {
    age: Number(d.age),
    region:
      d.region === "세종특별자치시" ? d.region : `${d.region} ${d.district}`,
    income_level: incomeWon(d),

    employment_status: d.employment as UserProfileInput["employment_status"],

    eligibility_conditions: {
      gender: d.gender as UserProfileInput["eligibility_conditions"]["gender"],
      household_size: d.householdSize ? Number(d.householdSize) : null,

      income_type:
        d.incomeType as UserProfileInput["eligibility_conditions"]["income_type"],
      asset_range: d.asset || null,

      housing_type: d.housing,
      owns_home: d.ownsHome === "UNKNOWN" ? null : d.ownsHome === "YES",

      disability_status: d.disability as "YES" | "NO" | "UNKNOWN",
      student_status: d.student as "YES" | "NO" | "UNKNOWN",

      marital_status:
        d.maritalStatus as UserProfileInput["eligibility_conditions"]["marital_status"],
      children_count: d.childrenCount ? Number(d.childrenCount) : null,

      qualifications: d.qualificationStatus === "YES" ? d.qualifications : [],

      additional_conditions: {
        qualification_status: d.qualificationStatus,
        profile_schema_version: 3,
        employment_detail: d.employment,
        basic_benefit_status: extra.basicBenefitStatus || null,
        basic_benefit_types:
          ["YES", "NO"].includes(extra.basicBenefitStatus) &&
          extra.basicBenefitTypes.length > 0
            ? extra.basicBenefitTypes
            : null,
        near_poverty_status: extra.nearPovertyStatus || null,
        single_parent_support_status: extra.singleParentSupportStatus || null,
        household_monthly_income_won: optionalNumber(
          extra.householdMonthlyIncomeWon,
        ),
        household_income_recognition_known:
          extra.householdIncomeRecognitionKnown || null,
        recognized_household_income_won:
          extra.householdIncomeRecognitionKnown === "YES"
            ? optionalNumber(extra.recognizedHouseholdIncomeWon)
            : null,
        household_basic_benefit_status:
          extra.householdBasicBenefitStatus || null,
        child_welfare_protection_experience:
          extra.childWelfareProtectionExperience || null,
        protection_ended: extra.protectionEnded || null,
        protection_end_month:
          extra.protectionEnded === "YES" ? extra.protectionEndMonth || null : null,
        protection_duration_months:
          extra.childWelfareProtectionExperience === "YES" &&
          extra.protectionEnded === "YES"
            ? optionalNumber(extra.protectionDurationMonths)
            : null,
        job_seek_registration: extra.jobSeekRegistration || null,
        employment_support_program: extra.employmentSupportProgram || null,
        self_sufficiency_program_status:
          extra.selfSufficiencyProgramStatus || null,
        registered_address_sido: extra.registeredAddressSido || null,
        registered_address_district: extra.registeredAddressDistrict || null,
        registered_residence_start_month:
          extra.registeredResidenceStartMonth || null,
      },
    },
  }
}

export function isDraft(value: unknown): value is ProfileDraft {
  if (!value || typeof value !== "object") return false

  const d = value as Record<string, unknown>

  if (
    d.additionalEligibility !== undefined &&
    (!d.additionalEligibility || typeof d.additionalEligibility !== "object")
  )
    return false

  if (d.additionalEligibility && !isAdditionalEligibilityDraft(d.additionalEligibility))
    return false

  if (
    !Object.keys(EMPTY_DRAFT).every((key) =>
      key === "qualifications"
        ? Array.isArray(d[key]) &&
          (d[key] as unknown[]).every(
            (v) =>
              typeof v === "string" && QUALIFICATIONS.some(([id]) => id === v),
          )
        : typeof d[key] === "string",
    )
  )
    return false

  const enums: Record<string, Option[]> = {
    age: numberOptions(19, 34),
    incomeMajor: numberOptions(0, 99),
    incomeMinor: numberOptions(0, 99),
    gender: GENDER,
    incomeType: INCOME,
    housing: HOUSING,
    ownsHome: YES_NO,
    householdSize: numberOptions(1, 20),
    asset: ASSETS,
    employment: EMPLOYMENT,
    disability: YES_NO,
    student: YES_NO,
    maritalStatus: MARRIAGE,
    childrenCount: numberOptions(0, 20),
    qualificationStatus: YES_NO,
  }

  return (
    Object.entries(enums).every(([key, options]) =>
      d[key] === ""
        ? EMPTY_DRAFT[(key as keyof ProfileDraft)] === ""
        : options.some(([v]) => v === d[key]),
    ) &&
    (d.region === ""
      ? d.district === ""
      : typeof d.region === "string" &&
        Object.prototype.hasOwnProperty.call(REGIONS, d.region) &&
        (d.district === "" || REGIONS[d.region].includes(d.district as string)))
  )
}

function isAdditionalEligibilityDraft(
  value: unknown,
): value is AdditionalEligibilityDraft {
  if (!value || typeof value !== "object") return false
  const additional = value as Record<string, unknown>
  const statusKeys = [
    "basicBenefitStatus",
    "nearPovertyStatus",
    "singleParentSupportStatus",
    "householdIncomeRecognitionKnown",
    "householdBasicBenefitStatus",
    "childWelfareProtectionExperience",
    "protectionEnded",
    "jobSeekRegistration",
    "employmentSupportProgram",
    "selfSufficiencyProgramStatus",
  ]
  return (
    Object.keys(EMPTY_ADDITIONAL_ELIGIBILITY).every((key) =>
      key === "basicBenefitTypes"
        ? Array.isArray(additional[key]) &&
          (additional[key] as unknown[]).every(
            (item) =>
              typeof item === "string" &&
              ["LIVELIHOOD", "MEDICAL", "HOUSING", "EDUCATION", "NONE"].includes(item),
          )
        : typeof additional[key] === "string",
    ) &&
    statusKeys.every((key) =>
      ["", "YES", "NO", "UNKNOWN"].includes(additional[key] as string),
    ) &&
    (additional.registeredAddressSido === "" ||
      (typeof additional.registeredAddressSido === "string" &&
        Object.prototype.hasOwnProperty.call(REGIONS, additional.registeredAddressSido))) &&
    (additional.registeredAddressDistrict === "" ||
      (typeof additional.registeredAddressSido === "string" &&
        REGIONS[additional.registeredAddressSido]?.includes(
          additional.registeredAddressDistrict as string,
        )))
  )
}
