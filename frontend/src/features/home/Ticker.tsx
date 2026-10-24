import { useState } from "react"

const items = [
  "월세 · 주거비 지원",
  "취업 준비 · 직업훈련",
  "저축 · 자산 형성",
  "마음건강 · 생활 지원",
  "내 조건에 맞는 정책",
  "조건 변화에 따른 새로운 기회",
]

export default function Ticker() {
  const [paused, setPaused] = useState(false)
  return (
    <section className="youth-ticker" aria-label="지원 분야 안내">
      <span className="youth-ticker-label">
        찾아볼 기회 <span aria-hidden="true">✦</span>
      </span>
      <div className="youth-ticker-window">
        <div
          className="youth-ticker-track"
          style={{
            animationPlayState: paused ? "paused" : "running",
          }}
        >
          {[0, 1].map((copy) => (
            <ul
              key={copy}
              aria-hidden={copy === 1 ? true : undefined}
              className="youth-ticker-group"
            >
              {items.map((item) => (
                <li key={item}>
                  <span aria-hidden="true">✦</span>
                  {item}
                </li>
              ))}
            </ul>
          ))}
        </div>
      </div>
      <button
        className="youth-ticker-toggle"
        onClick={() => setPaused((value) => !value)}
        aria-pressed={paused}
        aria-label={
          paused ? "지원 분야 목록 재생" : "지원 분야 목록 일시정지"
        }
      >
        {paused ? "재생 ▶" : "정지 Ⅱ"}
      </button>
    </section>
  )
}
