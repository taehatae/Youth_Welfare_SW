import type { CatalogPolicy } from "../../types/policyCatalog"

// 분야별 파스텔 배경·글자색과 커버에 크게 깔리는 짧은 단어
export const CATEGORY_STYLE: Record<string, { bg: string; ink: string; word: string }> = {
  housing: { bg: "#DDEBFF", ink: "#2357B0", word: "주거" },
  employment: { bg: "#D3F2E6", ink: "#17795A", word: "일자리" },
  finance: { bg: "#FFF0CC", ink: "#8F6100", word: "금융" },
  education: { bg: "#ECE7FD", ink: "#5B47C9", word: "교육" },
  health: { bg: "#FFE0E3", ink: "#B23A4A", word: "건강" },
  living: { bg: "#FFE9D6", ink: "#A5531A", word: "생활" },
  culture: { bg: "#E6F5C9", ink: "#4D7A12", word: "문화" },
  safety: { bg: "#DDF1F7", ink: "#1F6F86", word: "안전" },
  other: { bg: "#E8EEF4", ink: "#475569", word: "정책" },
}

// 분야 색 이름(홈 분야 카드·정책 찾기 분야 칩·목록 아이콘이 같은 색을 쓴다)
export const CATEGORY_TONE: Record<string, string> = {
  housing: "blue",
  employment: "mint",
  finance: "butter",
  education: "lav",
  health: "pink",
  living: "mint",
  culture: "butter",
  safety: "lav",
  other: "gray",
}

export const styleOf = (categories: string[]) =>
  CATEGORY_STYLE[categories.find((c) => c in CATEGORY_STYLE) ?? "other"]

// 지원 유형별 짧은 글리프와 이름 (목록 행의 아이콘 칸)
export function supportTypeOf(text: string | null | undefined): { glyph: string; label: string } {
  const t = text ?? ""
  if (/융자|대여|대출/.test(t)) return { glyph: "↺", label: "융자" }
  if (t.includes("바우처")) return { glyph: "V", label: "바우처" }
  if (t.includes("서비스")) return { glyph: "✓", label: "서비스" }
  if (t.includes("감면")) return { glyph: "%", label: "감면" }
  if (t.includes("현물")) return { glyph: "□", label: "현물" }
  if (/시설|입소/.test(t)) return { glyph: "⌂", label: "시설 입소" }
  if (/현금|지원금|수당|보조/.test(t)) return { glyph: "₩", label: "현금 지원" }
  return { glyph: "", label: "기타" }
}

// 목록 응답에 신청 마감일이 있으면(선택 필드) 쓴다. 없거나 상시면 null.
export function deadlineOf(policy: CatalogPolicy): number | null {
  const raw = (policy as CatalogPolicy & { apply_end?: string | null }).apply_end
  const m = raw?.match(/^(\d{4})-?(\d{2})-?(\d{2})$/)
  return m ? Date.UTC(+m[1], +m[2] - 1, +m[3]) : null
}
