import type { ReactNode } from "react"

// 공공 API 원문은 한 문단에 '※', ' - ', '①' 같은 항목이 이어 붙어 오는 경우가 많다.
// 이런 표시 앞에서 줄을 나누고, 나이·소득·제외처럼 자격 판단에 쓰이는 표현을 강조한다.
const BREAK_BEFORE = /\s*(?=※)|\s+(?=-\s)|\s+(?=[①-⑳])|\s+(?=\(\d+단계\))/g
const HIGHLIGHT =
  /(만?\s?\d+\s?세\s?[~∼-]\s?\d+\s?세(?:\s?(?:이상|이하|미만|초과))?|만\s?\d+\s?세(?:\s?(?:이상|이하|미만|초과))?|\d+\s?세\s?(?:이상|이하|미만|초과)|중위소득\s?\d+\s?%(?:\s?(?:이하|이상|미만|초과))?|\d+\s?%\s?(?:이하|이상|미만|초과)|\d[\d,.]*\s?(?:만원|억원|천만원)\s?(?:이하|이상|미만|초과)|제외|불가|할 수 없습니다)/g
const NEGATIVE = /^(제외|불가|할 수 없습니다)$/

type Line = { kind: "note" | "item" | "text"; text: string }

function lines(text: string): Line[] {
  return text
    .split("\n")
    .flatMap((line) => line.replace(BREAK_BEFORE, "\n").split("\n"))
    .map((line) => line.trim())
    .filter(Boolean)
    // 기호만 남은 줄('※')은 다음 줄과 합친다.
    .reduce<string[]>((merged, line) => {
      const last = merged[merged.length - 1]
      if (last && /^[※*]$/.test(last)) merged[merged.length - 1] = `${last} ${line}`
      else merged.push(line)
      return merged
    }, [])
    .map((line) =>
      line.startsWith("※") || line.startsWith("* ")
        ? { kind: "note", text: line }
        : /^(-|·|[①-⑳]|\(\d+단계\))/.test(line)
          ? { kind: "item", text: line.replace(/^-\s*/, "") }
          : { kind: "text", text: line },
    )
}

function highlight(text: string): ReactNode[] {
  return text.split(HIGHLIGHT).map((part, index) =>
    index % 2 === 1 ? (
      <mark key={index} data-tone={NEGATIVE.test(part) ? "negative" : undefined}>
        {part}
      </mark>
    ) : (
      part
    ),
  )
}

export default function PolicyText({ text }: { text: string }) {
  if (!text) return <p>제공된 정보가 없어요. 공식 공고에서 확인해주세요.</p>
  return (
    <div className="policy-text">
      {lines(text).map((line, index) =>
        line.kind === "item" ? (
          <p key={index} className="policy-text-item">
            {highlight(line.text)}
          </p>
        ) : (
          <p key={index} className={line.kind === "note" ? "policy-text-note" : undefined}>
            {highlight(line.text)}
          </p>
        ),
      )}
    </div>
  )
}
