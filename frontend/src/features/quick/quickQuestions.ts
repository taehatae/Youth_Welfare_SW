// 간편 정책 찾기 질문. 질문 id는 백엔드 quick_finder_service.QUESTIONS와 같다.
// 서버가 '이 분야 정책이 실제로 비교하는 조건'에 해당하는 질문 id만 내려 주고, 화면은 그 순서대로 묻는다.
// 답하지 않은 항목은 보내지 않는다. 0·미혼·대한민국·해당 없음 같은 값을 대신 채우지 않는다.
import {
  CREDIT_BUREAU, EMPLOYMENT, HOUSING, MARRIAGE, NATIONALITY, SCHOOL_LEVEL, SPECIAL_TARGETS, numberOptions, type Option,
} from "../../data/profileOptions"
import { REGIONS } from "../../data/regions"
import type { QuickAnswers } from "../../types/quickFinder"

// 값: 문자열(선택·숫자 입력), 문자열 배열(여러 개 선택). undefined나 ""는 미응답이다.
export type QuickDraft = Record<string, string | string[] | undefined>

type When = (d: QuickDraft) => boolean
export type QuickInput =
  | { kind: "choice"; key: string; label: string; options: Option[]; when?: When }
  | { kind: "number"; key: string; label: string; unit: string; min: number; max: number; won?: boolean; hint?: string; when?: When }
  // allowNone: '해당 없음'을 고르면 빈 목록을 보낸다(미응답과 구분).
  | { kind: "multi"; key: string; label: string; options: Option[]; allowNone?: boolean; when?: When }
  | { kind: "region"; key: string; label: string }
  | { kind: "age"; key: string; label: string }

export interface QuickQuestion {
  id: string
  prompt: string
  help?: string
  required?: boolean
  inputs: QuickInput[]
}

const YES_NO: Option[] = [["YES", "예"], ["NO", "아니요"]]
const yesNo = (key: string, label: string, when?: When): QuickInput => ({ kind: "choice", key, label, options: YES_NO, when })
const money = (key: string, label: string, hint?: string, when?: When): QuickInput =>
  ({ kind: "number", key, label, unit: "만원", min: 0, max: 100_000_000, won: true, hint, when })
const is = (key: string, value: string): When => (d) => d[key] === value

export const QUESTIONS: Record<string, QuickQuestion> = {
  age: { id: "age", required: true, prompt: "먼저 만 나이를 알려주세요.", help: "거의 모든 청년 정책이 나이를 봐요. 이 질문만 꼭 답해 주세요.",
    inputs: [{ kind: "age", key: "age", label: "만 나이" }] },
  region: { id: "region", prompt: "어디에 살고 있나요?", help: "주민등록상 주소 기준이에요.",
    inputs: [{ kind: "region", key: "region", label: "거주 지역" }] },
  income: { id: "income", prompt: "본인의 월 소득은 얼마인가요?", help: "세전 금액이에요. 소득이 없으면 0을 입력하세요.",
    inputs: [money("income_monthly_won", "본인 월 소득")] },
  employment: { id: "employment", prompt: "지금 고용 상태는 어떤가요?",
    inputs: [{ kind: "choice", key: "employment", label: "고용 상태", options: EMPLOYMENT }] },
  gender: { id: "gender", prompt: "성별을 알려주세요.", help: "성별이 대상 조건인 정책이 있어요.",
    inputs: [{ kind: "choice", key: "gender", label: "성별", options: [["MALE", "남성"], ["FEMALE", "여성"]] }] },
  household: { id: "household", prompt: "가구원은 본인 포함 몇 명인가요?", help: "주민등록상 같은 세대 기준이에요.",
    inputs: [{ kind: "number", key: "household_size", label: "가구원 수", unit: "명", min: 1, max: 20 }] },
  household_income: { id: "household_income", prompt: "가구 전체의 월 소득은 얼마인가요?", help: "가구원 모두의 세전 월 소득을 더한 금액이에요.",
    inputs: [money("household_monthly_income_won", "가구 월 소득")] },
  recognized_income: { id: "recognized_income", prompt: "가구 소득인정액을 알고 있나요?",
    help: "소득과 재산을 환산해 더한 금액이에요(복지로·주민센터에서 확인). 모르면 건너뛰세요. 가구 월 소득과 다른 값이에요.",
    inputs: [money("recognized_household_income_won", "월 소득인정액")] },
  household_assets: { id: "household_assets", prompt: "가구의 재산과 부채를 알려주세요.", help: "모르는 칸은 비워 두세요.",
    inputs: [money("asset_amount_won", "가구 총재산"), money("household_debt_won", "가구 부채")] },
  personal_assets: { id: "personal_assets", prompt: "본인 명의 재산과 부채를 알려주세요.", help: "모르는 칸은 비워 두세요.",
    inputs: [money("personal_asset_amount_won", "본인 총재산"), money("personal_debt_won", "본인 부채")] },
  car: { id: "car", prompt: "가구가 가진 자동차 가액은 얼마인가요?", help: "자동차가 없으면 0을 입력하세요.",
    inputs: [money("car_value_won", "자동차가액")] },
  housing_type: { id: "housing_type", prompt: "지금 어떤 형태로 살고 있나요?",
    inputs: [{ kind: "choice", key: "housing_type", label: "주거 형태", options: HOUSING }] },
  home_ownership: { id: "home_ownership", prompt: "주택 보유 상황을 알려주세요.",
    inputs: [yesNo("owns_home", "본인 명의 주택이 있나요?"), yesNo("household_homeless", "세대원 전원이 무주택인가요?")] },
  disability: { id: "disability", prompt: "등록 장애인인가요?",
    inputs: [yesNo("disability_status", "등록 장애인"),
      yesNo("severe_disability", "중증(심한 장애)인가요?", is("disability_status", "YES"))] },
  student: { id: "student", prompt: "지금 학교에 다니고 있나요?", help: "입학·복학 예정도 재학으로 봐요.",
    inputs: [yesNo("student_status", "재학 중"),
      { kind: "choice", key: "school_level", label: "학교 구분", options: SCHOOL_LEVEL, when: is("student_status", "YES") }] },
  marriage: { id: "marriage", prompt: "혼인 상태를 알려주세요.",
    inputs: [{ kind: "choice", key: "marital_status", label: "혼인 상태", options: MARRIAGE.filter(([v]) => v !== "UNKNOWN") },
      { kind: "number", key: "marriage_years", label: "혼인 기간", unit: "년", min: 0, max: 80, when: is("marital_status", "MARRIED") },
      money("spouse_monthly_income_won", "배우자 월 소득", undefined, is("marital_status", "MARRIED"))] },
  children: { id: "children", prompt: "자녀가 있나요?",
    inputs: [{ kind: "number", key: "children_count", label: "자녀 수", unit: "명", min: 0, max: 20 },
      { kind: "number", key: "youngest_child_age", label: "막내 자녀 나이", unit: "세", min: 0, max: 40,
        when: (d) => Number(d.children_count) > 0 }] },
  pregnancy: { id: "pregnancy", prompt: "본인 또는 배우자가 임신 중인가요?", inputs: [yesNo("pregnancy", "임신 중")] },
  nationality: { id: "nationality", prompt: "국적을 알려주세요.",
    inputs: [{ kind: "choice", key: "nationality", label: "국적", options: NATIONALITY }] },
  special_targets: { id: "special_targets", prompt: "아래 중 해당하는 것이 있나요?", help: "여러 개를 고를 수 있어요. 없으면 '해당 없음'을 고르세요.",
    inputs: [{ kind: "multi", key: "special_targets", label: "대상 구분", options: SPECIAL_TARGETS, allowNone: true }] },
  basic_benefit: { id: "basic_benefit", prompt: "기초생활보장 수급 상황을 알려주세요.",
    inputs: [yesNo("basic_benefit_status", "본인이 기초생활보장 수급자인가요?"),
      { kind: "multi", key: "basic_benefit_types", label: "받는 급여", when: is("basic_benefit_status", "YES"),
        options: [["LIVELIHOOD", "생계급여"], ["MEDICAL", "의료급여"], ["HOUSING", "주거급여"], ["EDUCATION", "교육급여"]] },
      yesNo("household_basic_benefit_status", "가구원 중 수급자가 있나요?")] },
  near_poverty: { id: "near_poverty", prompt: "차상위계층인가요?", inputs: [yesNo("near_poverty_status", "차상위계층")] },
  single_parent: { id: "single_parent", prompt: "한부모가족 지원 대상인가요?", inputs: [yesNo("single_parent_support_status", "한부모가족")] },
  job_seek: { id: "job_seek", prompt: "구직 등록을 했나요?", inputs: [yesNo("job_seek_registration", "구직 등록")] },
  protection: { id: "protection", prompt: "아동복지시설이나 가정위탁 보호를 받은 적이 있나요?",
    inputs: [yesNo("child_welfare_protection_experience", "보호 경험"),
      yesNo("protection_ended", "보호가 종료되었나요?", is("child_welfare_protection_experience", "YES"))] },
  credit: { id: "credit", prompt: "신용점수를 알고 있나요?", help: "평가사와 점수를 함께 입력하세요.",
    inputs: [{ kind: "choice", key: "credit_bureau", label: "평가사", options: CREDIT_BUREAU },
      { kind: "number", key: "credit_score", label: "신용점수", unit: "점", min: 0, max: 1000 }] },
}

export const AGE_OPTIONS = numberOptions(19, 34, "세")
export const questionsFor = (ids: string[]): QuickQuestion[] =>
  ids.flatMap((id) => (QUESTIONS[id] ? [QUESTIONS[id]] : []))

export const visibleInputs = (q: QuickQuestion, d: QuickDraft) =>
  q.inputs.filter((input) => !("when" in input) || !input.when || input.when(d))

const filled = (v: string | string[] | undefined) => (Array.isArray(v) ? true : v !== undefined && v !== "")
const regionValue = (d: QuickDraft) => {
  const sido = typeof d.region === "string" ? d.region : ""
  const district = typeof d.region_district === "string" ? d.region_district : ""
  if (!sido) return ""
  if (sido === "세종특별자치시") return sido
  return district ? `${sido} ${district}` : ""
}

export function isAnswered(q: QuickQuestion, d: QuickDraft): boolean {
  return visibleInputs(q, d).some((input) =>
    input.kind === "region" ? !!regionValue(d) : input.kind === "multi" ? Array.isArray(d[input.key]) &&
      (input.allowNone || (d[input.key] as string[]).length > 0) : filled(d[input.key]))
}

// 질문 하나의 입력 오류. 빈 칸은 '모름'이라 오류가 아니다.
export function questionError(q: QuickQuestion, d: QuickDraft): string {
  for (const input of visibleInputs(q, d)) {
    const v = d[input.key]
    if (input.kind === "age" && !AGE_OPTIONS.some(([a]) => a === v)) return "만 19~34세 중 나이를 골라 주세요."
    if (input.kind === "region" && typeof d.region === "string" && d.region && d.region !== "세종특별자치시" &&
        !REGIONS[d.region]?.includes(String(d.region_district ?? "")))
      return "시군구까지 골라 주세요. 모르면 시도 선택을 비우고 건너뛰세요."
    if (input.kind === "number" && typeof v === "string" && v !== "") {
      if (!/^\d+$/.test(v) || Number(v) < input.min || Number(v) > input.max)
        return `${input.label}은(는) ${input.min}~${input.max.toLocaleString("ko-KR")} 사이의 정수로 입력해 주세요.`
    }
  }
  if (q.id === "credit" && filled(d.credit_bureau) !== filled(d.credit_score)) return "평가사와 신용점수를 함께 입력하거나 둘 다 비워 주세요."
  if (q.id === "home_ownership" && d.owns_home === "NO" && d.housing_type === "OWNED")
    return "자가 거주를 골랐다면 본인 명의 주택 보유를 다시 확인해 주세요."
  if (q.id === "housing_type" && d.owns_home === "NO" && d.housing_type === "OWNED")
    return "본인 명의 주택이 없다고 했다면 주거 형태를 다시 확인해 주세요."
  return ""
}

// 서버로 보낼 값. 선택 분야의 질문 중 화면에 보이는 칸에 답한 값만 넣는다.
export function toAnswers(ids: string[], d: QuickDraft): QuickAnswers {
  const out: Record<string, string | number | string[]> = {}
  for (const q of questionsFor(ids)) {
    for (const input of visibleInputs(q, d)) {
      const v = d[input.key]
      if (input.kind === "region") { const region = regionValue(d); if (region) out.region = region; continue }
      if (input.kind === "multi") {
        if (Array.isArray(v) && (v.length > 0 || input.allowNone)) out[input.key] = [...v]
        continue
      }
      if (typeof v !== "string" || v === "") continue
      out[input.key] = input.kind === "age" ? Number(v) : input.kind === "number" ? Number(v) * (input.won ? 10000 : 1) : v
    }
  }
  if (typeof out.age !== "number") throw new Error("만 나이를 먼저 골라 주세요.")
  return out as QuickAnswers
}

// 사용자 말풍선에 보일 답 요약.
export function answerSummary(q: QuickQuestion, d: QuickDraft): string {
  if (!isAnswered(q, d)) return "건너뛰기 (확인 필요로 남겨요)"
  return visibleInputs(q, d).flatMap((input) => {
    const v = d[input.key]
    if (input.kind === "region") return regionValue(d) ? [regionValue(d)] : []
    if (input.kind === "age") return [`만 ${v}세`]
    if (input.kind === "multi") {
      if (!Array.isArray(v)) return []
      return [v.length ? v.map((x) => input.options.find(([o]) => o === x)?.[1] ?? x).join(", ") : "해당 없음"]
    }
    if (typeof v !== "string" || v === "") return []
    const text = input.kind === "number" ? `${Number(v).toLocaleString("ko-KR")}${input.unit}`
      : input.options.find(([o]) => o === v)?.[1] ?? v
    return [q.inputs.length > 1 ? `${input.label} ${text}` : text]
  }).join(" · ")
}
