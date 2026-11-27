import { useSyncExternalStore } from "react"

// 추천 경로용 개선 난이도 가중치를 사용자가 직접 정한다.
// 백엔드는 미충족 조건마다 기본 점수(difficulty)와 종류(difficulty_group)를 내려보내고,
// 화면은 종류별로 사용자가 고른 배율을 곱해 경로 순서를 다시 매긴다. 신청 가능 여부(판정)는 바뀌지 않는다.
export type DifficultyGroup = "apply" | "money" | "time" | "life" | "family" | "identity"
export type DifficultyPrefs = Record<DifficultyGroup, number>

export const DIFFICULTY_GROUPS: { id: DifficultyGroup; label: string; examples: string; base: string }[] = [
  { id: "apply", label: "신청·등록", examples: "구직 등록, 재학(입학·복학)", base: "1점" },
  { id: "money", label: "금액·비율", examples: "소득, 재산, 자동차가액", base: "2점 + 기준 대비 차이 10%마다 1점(최대 8점)" },
  { id: "time", label: "시간이 지나면 충족", examples: "나이 하한, 혼인 기간 하한", base: "남은 햇수" },
  { id: "life", label: "생활 변화", examples: "고용 상태, 주거 형태, 거주지, 부모와 따로 거주", base: "4점" },
  { id: "family", label: "가족·지위", examples: "혼인, 자녀, 임신, 한부모, 수급·차상위, 장애", base: "8점" },
  { id: "identity", label: "개인 신분", examples: "성별, 국적, 보훈, 북한이탈주민, 다문화", base: "20점" },
]

// 단계 → 배율. 3단계(보통)가 기본 점수 그대로다.
export const DIFFICULTY_LEVELS: { level: number; label: string; factor: number }[] = [
  { level: 1, label: "아주 쉬움", factor: 0.25 },
  { level: 2, label: "쉬움", factor: 0.5 },
  { level: 3, label: "보통", factor: 1 },
  { level: 4, label: "어려움", factor: 2 },
  { level: 5, label: "아주 어려움", factor: 4 },
]

export const DEFAULT_PREFS: DifficultyPrefs = { apply: 3, money: 3, time: 3, life: 3, family: 3, identity: 3 }
const KEY = "youth-welfare:difficulty-prefs"
const listeners = new Set<() => void>()
let current: DifficultyPrefs = load()

function load(): DifficultyPrefs {
  try {
    const raw = typeof localStorage !== "undefined" ? localStorage.getItem(KEY) : null
    const parsed = raw ? JSON.parse(raw) : {}
    const out = { ...DEFAULT_PREFS }
    for (const g of DIFFICULTY_GROUPS) {
      const v = parsed?.[g.id]
      if (Number.isInteger(v) && v >= 1 && v <= 5) out[g.id] = v
    }
    return out
  } catch {
    return { ...DEFAULT_PREFS }
  }
}

export const getDifficultyPrefs = () => current
export const isDefaultPrefs = (prefs: DifficultyPrefs) =>
  DIFFICULTY_GROUPS.every((g) => prefs[g.id] === DEFAULT_PREFS[g.id])

export function setDifficultyPrefs(next: DifficultyPrefs) {
  current = { ...next }
  try { localStorage.setItem(KEY, JSON.stringify(current)) } catch { /* 저장이 막혀도 이번 화면에서는 적용한다 */ }
  for (const listener of listeners) listener()
}

export function subscribeDifficultyPrefs(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export const useDifficultyPrefs = () =>
  useSyncExternalStore(subscribeDifficultyPrefs, getDifficultyPrefs, getDifficultyPrefs)

// 조건 하나의 점수 = 기본 점수 × 그 종류의 배율. 종류가 없는 이전 결과는 기본 점수 그대로.
export function weighted(difficulty: number | null | undefined, group: string | null | undefined, prefs: DifficultyPrefs) {
  if (difficulty == null) return 0
  const level = (prefs as Record<string, number>)[group ?? ""]
  const factor = DIFFICULTY_LEVELS.find((l) => l.level === level)?.factor ?? 1
  return difficulty * factor
}
