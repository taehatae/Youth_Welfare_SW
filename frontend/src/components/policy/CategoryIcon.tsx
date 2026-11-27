// 정책 분야 아이콘(선 그림). 색은 currentColor를 따른다.
const PATHS: Record<string, string[]> = {
  housing: ["M3 10.5 12 3l9 7.5", "M5 9v11h14V9", "M10 20v-6h4v6"],
  employment: ["M3 8h18v12H3z", "M8 8V5h8v3", "M3 13h18"],
  finance: ["M3 7h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M3 7l12-4 2 4", "M16 13.5h2"],
  education: ["M2 9l10-5 10 5-10 5z", "M6 11v5c3 2.5 9 2.5 12 0v-5", "M22 9v6"],
  health: ["M12 20s-8-4.5-8-10a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 5.5-8 10-8 10z", "M8 11h2l1-2 2 4 1-2h2"],
  living: ["M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6z", "M17 11a2.5 2.5 0 1 0 0-5", "M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6", "M16 14c2.8 0 5 2.3 5 6"],
  culture: ["M9 18V6l11-2v12", "M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0z", "M20 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z"],
  safety: ["M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z", "M8.5 12l2.5 2.5 4.5-5"],
  other: ["M4 4h7v7H4z", "M13 4h7v7h-7z", "M4 13h7v7H4z", "M13 13h7v7h-7z"],
  all: ["M4 6h16", "M4 12h16", "M4 18h10"],
}

export default function CategoryIcon({ id, size = 28 }: { id: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {(PATHS[id] ?? PATHS.other).map((d) => <path key={d} d={d} />)}
    </svg>
  )
}
