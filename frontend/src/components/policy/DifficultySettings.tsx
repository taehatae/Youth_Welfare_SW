import {
  DEFAULT_PREFS, DIFFICULTY_GROUPS, DIFFICULTY_LEVELS, isDefaultPrefs, setDifficultyPrefs, useDifficultyPrefs,
} from "../../services/difficultyPrefs"

// 추천 기준 보기·바꾸기: 조건 종류마다 사용자가 체감하는 어려움을 고르면 모든 정책의 추천 경로 순서가 바로 바뀐다.
// 신청 가능 여부(판정)는 바뀌지 않는다. 설정은 이 브라우저에만 저장된다.
export default function DifficultySettings({ disabled = false }: { disabled?: boolean }) {
  const prefs = useDifficultyPrefs()
  const custom = !isDefaultPrefs(prefs)
  return (
    <details className="difficulty-rules">
      <summary>추천 기준 보기·바꾸기{custom ? " (내 기준 적용 중)" : ""}</summary>
      <p>
        맞지 않는 조건마다 아래 점수를 매겨, 합이 가장 낮은 경로를 추천해요. 나에게 더 쉽거나 어려운 종류가 있다면
        골라 주세요. 모든 정책의 추천 경로가 바로 다시 정해져요. 신청 가능 여부는 바뀌지 않아요.
      </p>
      {disabled && <p>전용 난이도를 확인하기 전에는 저장된 경로 순위를 표시해요.</p>}
      <ul className="difficulty-editor">
        {DIFFICULTY_GROUPS.map((g) => (
          <li key={g.id}>
            <div>
              <b>{g.label}</b>
              <small>{g.examples} · 기본 {g.base}</small>
            </div>
            <select
              disabled={disabled}
              aria-label={`${g.label} 조건의 난이도`}
              value={prefs[g.id]}
              onChange={(e) => setDifficultyPrefs({ ...prefs, [g.id]: Number(e.target.value) })}
            >
              {DIFFICULTY_LEVELS.map((l) => (
                <option key={l.level} value={l.level}>{l.label}{l.factor === 1 ? "" : ` (×${l.factor})`}</option>
              ))}
            </select>
          </li>
        ))}
      </ul>
      {custom && (
        <button type="button" disabled={disabled} className="difficulty-reset" onClick={() => setDifficultyPrefs(DEFAULT_PREFS)}>
          기본 기준으로 되돌리기
        </button>
      )}
    </details>
  )
}
