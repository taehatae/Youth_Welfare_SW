import PageHeading from "../../components/layout/PageHeading"
import { useEffect, useRef, useState } from "react"
import type { Page } from "../../types/page"
import type { UserProfileInput } from "../../types/welfareApi"
import { REGIONS } from "../../data/regions"
import {
  ASSETS,
  EMPTY_ADDITIONAL_ELIGIBILITY,
  EMPLOYMENT,
  GENDER,
  HOUSING,
  INCOME,
  MARRIAGE,
  QUALIFICATIONS,
  YES_NO,
  incomeWon,
  numberOptions,
  stepError,
  toProfile,
  type Option,
  type AdditionalEligibilityDraft,
  type ProfileDraft,
} from "../../data/profileOptions"

const YES_NO_UNKNOWN_OPTIONS: Option[] = [
  ["YES", "예"],
  ["NO", "아니요"],
  ["UNKNOWN", "모름·확인 필요"],
]
const BENEFIT_TYPE_OPTIONS: Option[] = [
  ["LIVELIHOOD", "생계급여"],
  ["MEDICAL", "의료급여"],
  ["HOUSING", "주거급여"],
  ["EDUCATION", "교육급여"],
]

const steps = [
  "기본 정보",
  "거주 지역",
  "소득",
  "가구 · 주거",
  "고용",
  "추가 조건",
]
function Select({
  name,
  label,
  value,
  options,
  onChange,
  hint,
  required = false,
  disabled = false,
  showUnanswered = false,
}: {
  name: string
  label: string
  value: string
  options: Option[]
  onChange: (value: string) => void
  hint?: string
  required?: boolean
  disabled?: boolean
  showUnanswered?: boolean
}) {
  return (
    <div className="space-y-2">
      <label
        htmlFor={name}
        className="block text-sm font-semibold text-slate-800"
      >
        {label}
        {required && <span className="ml-1 text-blue-700"> (필수)</span>}
      </label>
      <select
        id={name}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        required={required}
        aria-describedby={hint ? name + "-hint" : undefined}
        className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-base text-slate-900 focus:outline-2 focus:outline-blue-600 disabled:bg-slate-100"
      >
        {(showUnanswered || !options.some(([v]) => v === "UNKNOWN")) && (
          <option value="">
            {required ? "선택해주세요" : showUnanswered ? "미입력" : "미확인"}
          </option>
        )}
        {options.map(([id, text]) => (
          <option key={id} value={id}>
            {text}
          </option>
        ))}
      </select>
      {hint && (
        <p
          id={name + "-hint"}
          className="text-sm leading-relaxed text-slate-500"
        >
          {hint}
        </p>
      )}
    </div>
  )
}

export default function DiagnosisPage({
  draft,
  setDraft,
  step,
  setStep,
  onComplete,
  busy,
  setPage,
}: {
  draft: ProfileDraft
  setDraft: (value: ProfileDraft) => void
  step: number
  setStep: (value: number) => void
  onComplete: (profile: UserProfileInput) => Promise<void>
  busy: boolean
  setPage: (page: Page) => void
}) {
  const [error, setError] = useState("")
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    setError("")
    heading.current?.focus()
  }, [step])
  const update = (key: keyof ProfileDraft, value: string) => {
    const next = { ...draft, [key]: value }
    if (key === "region")
      next.district = value === "세종특별자치시" ? value : ""
    if (key === "incomeType" && value === "NONE") {
      next.incomeMajor = "0"
      next.incomeMinor = "0"
    }
    if (key === "qualificationStatus" && value !== "YES")
      next.qualifications = []
    setDraft(next)
    setError("")
  }
  const additional = {
    ...EMPTY_ADDITIONAL_ELIGIBILITY,
    ...draft.additionalEligibility,
  }
  const updateAdditional = (
    key: keyof AdditionalEligibilityDraft,
    value: string | string[],
  ) => {
    const next = { ...additional, [key]: value }
    if (key === "basicBenefitStatus") {
      next.basicBenefitTypes = value === "NO" ? ["NONE"] : []
    }
    if (key === "registeredAddressSido")
      next.registeredAddressDistrict = ""
    if (
      key === "householdIncomeRecognitionKnown" &&
      value !== "YES"
    ) {
      next.recognizedHouseholdIncomeWon = ""
    }
    if (
      key === "childWelfareProtectionExperience" &&
      value !== "YES"
    ) {
      next.protectionEnded = ""
      next.protectionEndMonth = ""
      next.protectionDurationMonths = ""
    }
    if (key === "protectionEnded" && value !== "YES") {
      next.protectionEndMonth = ""
      next.protectionDurationMonths = ""
    }
    setDraft({ ...draft, additionalEligibility: next })
    setError("")
  }
  const additionalSelect = (
    key: Exclude<keyof AdditionalEligibilityDraft, "basicBenefitTypes">,
    label: string,
    hint?: string,
  ) => (
    <Select
      name={`additional-${key}`}
      label={label}
      options={YES_NO_UNKNOWN_OPTIONS}
      value={additional[key]}
      onChange={(value) => updateAdditional(key, value)}
      hint={hint}
      showUnanswered
    />
  )
  const field = (
    key: Exclude<keyof ProfileDraft, "qualifications" | "additionalEligibility">,
    label: string,
    options: Option[],
    hint?: string,
    required = false,
    disabled = false,
  ) => (
    <Select
      name={key}
      label={label}
      options={options}
      value={draft[key]}
      onChange={(value) => update(key, value)}
      hint={hint}
      required={required}
      disabled={disabled}
    />
  )
  const proceed = async () => {
    const issue = stepError(draft, step)
    if (issue) {
      setError(issue)
      return
    }
    if (step < 5) {
      setStep(step + 1)
      return
    }
    try {
      await onComplete(toProfile(draft))
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "진단을 완료하지 못했어요. 다시 시도해주세요.",
      )
    }
  }
  return (
    <section className="mx-auto max-w-2xl px-4 py-8 pb-28 sm:px-6">
      <PageHeading eyebrow="내 정보에서 시작하는 맞춤 진단" title="내 자격 진단" description="입력 중인 내용은 이 브라우저에 저장됩니다. 모르는 추가 조건은 미확인으로 두세요." />
      <ol
        aria-label="진단 진행 단계"
        className="interface-steps my-6 grid grid-cols-3 gap-2 sm:grid-cols-6"
      >
        {steps.map((label, index) => (
          <li
            key={label}
            aria-current={index === step ? "step" : undefined}
            className={`rounded-lg px-2 py-2 text-center text-xs font-semibold ${
              index === step
                ? "bg-blue-700 text-white"
                : index < step
                  ? "bg-blue-50 text-blue-800"
                  : "bg-slate-100 text-slate-500"
            }`}
          >
            <button
              type="button"
              disabled={busy || index > step}
              onClick={() => setStep(index)}
              className="w-full rounded py-1 disabled:cursor-default"
              aria-label={label + (index < step ? " 수정" : "")}
            >
              {index + 1}. {label}
            </button>
          </li>
        ))}
      </ol>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void proceed()
        }}
        className="interface-form bg-white p-5 sm:p-7"
      >
        <h2
          ref={heading}
          tabIndex={-1}
          className="mb-6 text-xl font-bold text-slate-900 outline-none"
        >
          {steps[step]}{" "}
          <span className="text-sm font-normal text-slate-500">
            {step + 1} / 6
          </span>
        </h2>
        <fieldset disabled={busy} className="space-y-6">
          <legend className="sr-only">{steps[step]} 입력</legend>
          {step === 0 && (
            <>
              {field(
                "age",
                "만 나이",
                numberOptions(19, 34, "세"),
                "현재 진단은 만 19~34세를 대상으로 합니다.",
                true,
              )}
              {field("gender", "성별", GENDER)}
              <button
                type="button"
                onClick={() => setPage("explorer")}
                className="text-sm text-blue-700 underline underline-offset-4"
              >
                대상 연령 밖이라면 정책 목록 살펴보기
              </button>
            </>
          )}
          {step === 1 && (
            <>
              {field(
                "region",
                "시도",
                Object.keys(REGIONS).map((v) => [v, v]),
                "주민등록상 거주지를 선택해주세요.",
                true,
              )}
              {field(
                "district",
                "시군구",
                (REGIONS[draft.region] ?? []).map((v) => [v, v]),
                undefined,
                true,
                !draft.region,
              )}
            </>
          )}
          {step === 2 && (
            <>
              {field(
                "incomeType",
                "주된 소득 종류",
                INCOME,
                "여러 소득이 있다면 가장 큰 비중의 소득원을 선택해주세요.",
              )}
              <div>
                <p className="mb-3 text-sm font-semibold">
                  본인 월평균 세전 소득 (필수)
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {field(
                    "incomeMajor",
                    "백만원 단위",
                    numberOptions(0, 99).map(([v]) => [
                      v,
                      Number(v) * 100 + "만원",
                    ]),
                    undefined,
                    true,
                    draft.incomeType === "NONE",
                  )}
                  {field(
                    "incomeMinor",
                    "나머지 만원 단위",
                    numberOptions(0, 99, "만원"),
                    undefined,
                    true,
                    draft.incomeType === "NONE",
                  )}
                </div>
                <p
                  className="mt-3 rounded-lg bg-blue-50 p-3 text-sm text-blue-900"
                  aria-live="polite"
                >
                  {draft.incomeMajor !== "" && draft.incomeMinor !== ""
                    ? "선택한 월 소득: " +
                      incomeWon(draft).toLocaleString("ko-KR") +
                      "원"
                    : "예: 215만원 → 200만원 + 15만원"}
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  모든 소득을 합산해 만원 단위로 선택해주세요 (0~9,999만원).
                  가구소득과 소득인정액은 정책별로 추가 확인이 필요합니다.
                </p>
              </div>
            </>
          )}
          {step === 3 && (
            <>
              {field(
                "householdSize",
                "주민등록상 가구원 수",
                numberOptions(1, 20, "명"),
                "정책에서 사용하는 가구 범위는 다를 수 있어요.",
              )}
              {field("housing", "현재 주거 형태", HOUSING, undefined, true)}
              {field(
                "ownsHome",
                "본인 명의 주택 보유 여부",
                YES_NO,
                "현재 거주 형태와 별개로 다른 곳에 보유한 주택도 포함합니다.",
              )}
              {field(
                "asset",
                "본인 총재산 구간",
                ASSETS,
                "부채 차감 전 부동산·금융재산 등의 합계입니다. 정책별 산정액과는 다를 수 있어요.",
              )}
            </>
          )}
          {step === 4 && (
            <>
              {field(
                "employment",
                "현재 고용 상태",
                EMPLOYMENT,
                "학생 여부는 다음 단계에서 별도로 선택합니다. 재학 중 아르바이트를 한다면 아르바이트를 선택해주세요.",
                true,
              )}
            </>
          )}
          {step === 5 && (
            <>
              {field("student", "현재 재학 여부", YES_NO)}
              {field("disability", "등록 장애인 여부", YES_NO)}
              {field("maritalStatus", "혼인 상태", MARRIAGE)}
              {field("childrenCount", "자녀 수", numberOptions(0, 20, "명"))}
              {field("qualificationStatus", "보유 자격증 여부", YES_NO)}
              {draft.qualificationStatus === "YES" && (
                <fieldset className="space-y-2">
                  <legend className="mb-2 text-sm font-semibold">
                    보유 자격 (복수 선택)
                  </legend>
                  {QUALIFICATIONS.map(([value, label]) => (
                    <label
                      key={value}
                      className="flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 px-3 py-3 text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={draft.qualifications.includes(value)}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            qualifications: e.target.checked
                              ? [...draft.qualifications, value]
                              : draft.qualifications.filter((v) => v !== value),
                          })
                        }
                        className="h-4 w-4 accent-blue-700"
                      />
                      {label}
                    </label>
                  ))}
                  <p className="text-sm text-slate-500">
                    목록 밖 자격은 보유 여부만 저장하며, 자동 충족으로 판정하지
                    않습니다.
                  </p>
                </fieldset>
              )}

              <details className="rounded-xl border border-slate-200 p-4">
                <summary className="cursor-pointer font-semibold text-slate-900">
                  복지 수급·가구 소득 등 추가 정보 입력 (선택)
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-slate-600">
                  모르면 ‘모름·확인 필요’를 선택하고, 입력하지 않으면 미입력으로 저장됩니다.
                  입력 내용은 본인 응답이며 공식 자격 증명으로 간주되지 않습니다.
                </p>
                <div className="mt-5 space-y-7">
                  <fieldset className="space-y-5 border-t border-slate-200 pt-5">
                    <legend className="px-1 font-semibold">복지 수급·자격 정보</legend>
                    {additionalSelect("basicBenefitStatus", "기초생활보장급여 수급 여부")}
                    {additional.basicBenefitStatus === "YES" && (
                      <fieldset className="space-y-2">
                        <legend className="text-sm font-semibold">
                          수급 중인 급여 종류 (복수 선택)
                        </legend>
                        <p className="text-sm text-slate-500">
                          현재 해당하는 급여를 모두 선택해주세요.
                        </p>
                        {BENEFIT_TYPE_OPTIONS.map(([value, label]) => (
                          <label key={value} className="flex items-center gap-3 py-1 text-sm">
                            <input
                              type="checkbox"
                              checked={additional.basicBenefitTypes.includes(value)}
                              onChange={(event) =>
                                updateAdditional(
                                  "basicBenefitTypes",
                                  event.target.checked
                                    ? [...additional.basicBenefitTypes, value]
                                    : additional.basicBenefitTypes.filter((item) => item !== value),
                                )
                              }
                              className="h-4 w-4 accent-blue-700"
                            />
                            {label}
                          </label>
                        ))}
                      </fieldset>
                    )}
                    {additional.basicBenefitStatus === "NO" && (
                      <p className="text-sm text-slate-600">수급 급여 종류: 해당 없음</p>
                    )}
                    {additionalSelect("nearPovertyStatus", "차상위계층 해당 여부")}
                    {additionalSelect(
                      "singleParentSupportStatus",
                      "한부모가족 지원 대상 여부",
                    )}
                  </fieldset>

                  <fieldset className="space-y-5 border-t border-slate-200 pt-5">
                    <legend className="px-1 font-semibold">가구 소득 정보</legend>
                    <label className="block space-y-2 text-sm font-semibold text-slate-800">
                      가구 전체 월소득 (원, 선택)
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={additional.householdMonthlyIncomeWon}
                        onChange={(event) =>
                          updateAdditional("householdMonthlyIncomeWon", event.target.value)
                        }
                        className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-base font-normal"
                      />
                    </label>
                    {additionalSelect(
                      "householdIncomeRecognitionKnown",
                      "가구 소득인정액을 알고 있나요?",
                    )}
                    {additional.householdIncomeRecognitionKnown === "YES" && (
                      <label className="block space-y-2 text-sm font-semibold text-slate-800">
                        가구 소득인정액 (원, 선택)
                        <input
                          type="number"
                          min="0"
                          step="1"
                          value={additional.recognizedHouseholdIncomeWon}
                          onChange={(event) =>
                            updateAdditional("recognizedHouseholdIncomeWon", event.target.value)
                          }
                          className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-base font-normal"
                        />
                      </label>
                    )}
                    {additionalSelect(
                      "householdBasicBenefitStatus",
                      "가구 내 기초생활보장급여 수급자 여부",
                    )}
                    <p className="text-sm text-slate-500">
                      본인 월소득과 가구 월소득·소득인정액은 별도로 저장하며, 모르는 금액은 계산하지 않습니다.
                    </p>
                  </fieldset>

                  <fieldset className="space-y-5 border-t border-slate-200 pt-5">
                    <legend className="px-1 font-semibold">보호 경험·종료 정보</legend>
                    {additionalSelect(
                      "childWelfareProtectionExperience",
                      "아동복지시설 또는 가정위탁 보호 경험 여부",
                    )}
                    {additional.childWelfareProtectionExperience === "YES" && (
                      <>
                        {additionalSelect("protectionEnded", "보호 종료 여부")}
                        {additional.protectionEnded === "YES" && (
                          <>
                            <label className="block space-y-2 text-sm font-semibold text-slate-800">
                              보호 종료 연월 (선택)
                              <input
                                type="month"
                                value={additional.protectionEndMonth}
                                onChange={(event) =>
                                  updateAdditional("protectionEndMonth", event.target.value)
                                }
                                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-base font-normal"
                              />
                            </label>
                            <label className="block space-y-2 text-sm font-semibold text-slate-800">
                              보호 기간 (개월, 선택)
                              <input
                                type="number"
                                min="0"
                                step="1"
                                value={additional.protectionDurationMonths}
                                onChange={(event) =>
                                  updateAdditional("protectionDurationMonths", event.target.value)
                                }
                                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-base font-normal"
                              />
                            </label>
                          </>
                        )}
                      </>
                    )}
                  </fieldset>

                  <fieldset className="space-y-5 border-t border-slate-200 pt-5">
                    <legend className="px-1 font-semibold">구직·취업지원·자활 정보</legend>
                    {additionalSelect("jobSeekRegistration", "구직 등록 여부")}
                    {additionalSelect(
                      "employmentSupportProgram",
                      "취업지원 프로그램 참여 여부",
                    )}
                    {additionalSelect(
                      "selfSufficiencyProgramStatus",
                      "자활사업 참여 여부",
                    )}
                  </fieldset>

                  <fieldset className="space-y-5 border-t border-slate-200 pt-5">
                    <legend className="px-1 font-semibold">주민등록 주소·거주 기간 정보</legend>
                    <p className="text-sm text-slate-500">
                      지역과 거주 시작 시점은 참고 정보이며, 별도 증빙이 필요한 조건은 추가 확인으로 남습니다.
                    </p>
                    <Select
                      name="additional-registeredAddressSido"
                      label="주민등록상 시도"
                      options={Object.keys(REGIONS).map((value) => [value, value])}
                      value={additional.registeredAddressSido}
                      onChange={(value) =>
                        updateAdditional("registeredAddressSido", value)
                      }
                      showUnanswered
                    />
                    <Select
                      name="additional-registeredAddressDistrict"
                      label="주민등록상 시군구"
                      options={(REGIONS[additional.registeredAddressSido] ?? []).map(
                        (value) => [value, value],
                      )}
                      value={additional.registeredAddressDistrict}
                      onChange={(value) =>
                        updateAdditional("registeredAddressDistrict", value)
                      }
                      disabled={!additional.registeredAddressSido}
                      showUnanswered
                    />
                    <label className="block space-y-2 text-sm font-semibold text-slate-800">
                      주민등록상 거주 시작 연월 (선택)
                      <input
                        type="month"
                        value={additional.registeredResidenceStartMonth}
                        onChange={(event) =>
                          updateAdditional("registeredResidenceStartMonth", event.target.value)
                        }
                        className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-base font-normal"
                      />
                    </label>
                  </fieldset>
                </div>
              </details>
            </>
          )}
        </fieldset>
        {error && (
          <p
            role="alert"
            className="mt-5 rounded-lg bg-red-50 p-3 text-sm text-red-800"
          >
            {error}
          </p>
        )}
        <div className="mt-8 flex gap-3">
          {step > 0 && (
            <button
              type="button"
              disabled={busy}
              onClick={() => setStep(step - 1)}
              className="rounded-xl border border-slate-300 px-5 py-3 font-semibold disabled:opacity-50"
            >
              이전
            </button>
          )}
          <button
            type="submit"
            disabled={busy}
            className="interface-primary flex-1"
          >
            {busy ? "진단 중…" : step === 5 ? "이 정보로 진단하기" : "다음"}
          </button>
        </div>
      </form>
    </section>
  )
}
