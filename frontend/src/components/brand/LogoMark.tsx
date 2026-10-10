// Inspired by the 5th variant: J-mark + check + sprout leaf
export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <rect width="32" height="32" rx="8" fill="#1D4ED8"/>
      {/* J shape */}
      <path d="M18 8h4v13c0 3.3-2.7 6-6 6s-6-2.7-6-6h3.5c0 1.4 1.1 2.5 2.5 2.5s2.5-1.1 2.5-2.5V8z" fill="white"/>
      {/* Check mark inside shield area */}
      <path d="M10 14l2.5 2.5L17 11" stroke="#22C55E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Sprout */}
      <path d="M21 9c0-2 1.5-3.5 3.5-3.5" stroke="#22C55E" strokeWidth="1.5" strokeLinecap="round"/>
      <circle cx="24.5" cy="5.5" r="1.5" fill="#22C55E"/>
    </svg>
  )
}
