import type { Page } from "../../types/page"

import { BrandLogo } from "../../components/brand/BrandLogo"

import Ticker from "./Ticker"

import "./home.css"

const categories = [
  {
    icon: "⌂",
    title: "주거",
    category: "housing",
    subtitle: "나의 독립을 위한 준비",
    detail: "월세 · 전세 · 주거비",
    className: "youth-category-blue",
  },

  {
    icon: "↗",
    title: "취업",
    category: "employment",
    subtitle: "다음 커리어의 시작",
    detail: "구직 · 직업훈련 · 취업",
    className: "youth-category-green",
  },

  {
    icon: "₩",
    title: "금융",
    category: "finance",
    subtitle: "차곡차곡 만드는 내일",
    detail: "저축 · 자산 형성 · 금융",
    className: "youth-category-yellow",
  },

  {
    icon: "✳",
    title: "생활",
    category: "living",
    subtitle: "일상을 지탱하는 지원",
    detail: "생활비 · 돌봄 · 일상 지원",
    className: "youth-category-purple",
  },
]

export default function HomePage({
  setPage,
}: {
  setPage: (page: Page) => void
}) {
  return (
    <div className="youth-home">
      <Ticker />
      <section className="youth-hero">
        <div className="youth-home-width youth-hero-grid">
          <div className="youth-hero-copy">
            <p data-reveal className="youth-eyebrow">
              <span aria-hidden="true">✦</span> 청년의 다음 기회를 찾다
            </p>
            <h1 data-reveal data-reveal-delay="1">
              지금의 나에게,
              <br />
              <span>가능한 복지부터.</span>
            </h1>
            <p
              data-reveal
              data-reveal-delay="2"
              className="youth-hero-description"
            >
              내 조건에 맞는 지원을 찾고,
              <br />
              조금만 달라지면 가능한 기회까지 살펴보세요.
            </p>
            <div
              data-reveal
              data-reveal-delay="3"
              className="youth-hero-actions"
            >
              <button
                onClick={() => setPage("diagnosis")}
                className="youth-primary"
              >
                내 자격 진단하기 <span aria-hidden="true">↗</span>
              </button>
              <button
                onClick={() => setPage("dashboard")}
                className="youth-secondary"
              >
                나의 현황 보기 <span aria-hidden="true">→</span>
              </button>
            </div>
            <p className="youth-hero-note">
              만 19~34세 대상 · 나이부터 추가 조건까지, 선택으로 간편하게
            </p>
            <div className="youth-value-tags">
              <span>✓ 맞춤 정책 확인</span>
              <span>△ 부족한 조건 탐색</span>
              <span>↻ 정책 변화 조회</span>
            </div>
          </div>

          <div
            data-reveal
            data-reveal-delay="3"
            className="youth-preview"
            aria-label="진단과 현황 기능 소개"
          >
            <div className="youth-preview-top">
              <span>나의 기회 지도</span>
              <span className="youth-example-label">기능 미리보기</span>
            </div>
            <div className="youth-profile-strip">
              <span className="youth-profile-icon" aria-hidden="true">
                ✓
              </span>
              <div>
                <strong>출발점은, 내 정보</strong>
                <p>거주지 · 소득 · 주거 · 고용 상태</p>
              </div>
              <span className="youth-spark" aria-hidden="true">
                ✦
              </span>
            </div>
            <div className="youth-preview-card">
              <div className="youth-card-kicker">
                <span>01 / 진단 결과</span>
                <span className="youth-status-dot">조건 비교</span>
              </div>
              <h2>어떤 지원이 나와 맞을까?</h2>
              <div className="youth-condition-list">
                <div>
                  <span>입력값과 맞는 정책</span>
                  <span className="youth-condition-pass">신청 가능 ✓</span>
                </div>
                <div>
                  <span>맞지 않는 조건이 있는 정책</span>
                  <span className="youth-condition-gap">신청 불가 ✕</span>
                </div>
              </div>
              <p>충족한 조건 수와 부족한 조건을 함께 확인해요.</p>
            </div>
            <div className="youth-next-card">
              <span className="youth-refresh-icon" aria-hidden="true">
                ↻
              </span>
              <div>
                <p>02 / 나의 현황</p>
                <h2>조건은 저장하고, 기회는 다시 찾고.</h2>
                <span>새로 조회된 정책 · 신청 기간 변화 확인</span>
              </div>
            </div>
            <p className="youth-preview-caption">
              기능을 설명하는 화면이며 실제 진단 결과가 아닙니다.
            </p>
          </div>
        </div>
      </section>

      <section
        className="youth-topics youth-home-width"
        aria-labelledby="topics-title"
      >
        <div data-reveal className="youth-section-heading">
          <div>
            <p className="youth-section-label">내 생활과 가까운 지원</p>
            <h2 id="topics-title">어떤 기회를 찾고 있나요?</h2>
          </div>
          <button
            onClick={() => setPage("explorer")}
            className="youth-text-link"
          >
            정책 예시 둘러보기 <span aria-hidden="true">↗</span>
          </button>
        </div>
        <div className="youth-category-grid">
          {categories.map((category, index) => (
            <article
              data-reveal
              data-reveal-delay={index % 3}
              key={category.title}
              className={`youth-category ${category.className}`}
            >
              <div className="youth-category-top">
                <span className="youth-category-icon" aria-hidden="true">
                  {category.icon}
                </span>
                <span className="youth-category-name">{category.title}</span>
              </div>
              <h3>{category.subtitle}</h3>
              <p>{category.detail}</p>
              <a className="youth-category-link" href={"#explorer?category="+category.category}>{category.title} 정책 보기 <span aria-hidden="true">↗</span></a>
            </article>
          ))}
        </div>
        <p className="youth-section-note">
          지원 분야를 소개하는 예시입니다. 개별 정책의 자격과 신청 기간은 진단
          결과와 공식 공고를 확인해주세요.
        </p>
      </section>

      <section className="youth-journey" aria-labelledby="journey-title">
        <div className="youth-home-width youth-journey-inner">
          <div data-reveal className="youth-journey-heading">
            <p>자격있청 이용 방법</p>
            <h2 id="journey-title">
              오늘의 진단을
              <br />
              다음 기회로 연결해요.
            </h2>
            <span>진단 기록은 그대로, 현황은 새롭게.</span>
          </div>
          <ol className="youth-journey-steps">
            {[
              [
                "01",
                "내 정보 선택",
                "선택 항목과 필요한 추가 정보로 내 조건을 알려주세요.",
              ],

              [
                "02",
                "결과와 조건 확인",
                "맞춤 정책과 미충족 조건을 진단 당시 기록으로 확인해요.",
              ],

              [
                "03",
                "현황 새로고침",
                "저장된 정보로 다시 조회하고 추가된 정책과 종료된 신청을 살펴봐요.",
              ],
            ].map(([n, title, description], index) => (
              <li data-reveal data-reveal-delay={index % 3} key={n}>
                <span className="youth-step-number">{n}</span>
                <h3>{title}</h3>
                <p>{description}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>
      <footer data-reveal className="youth-home-width youth-home-footer">
        <BrandLogo width={112} />
        <p>내 조건을 이해하고, 다음 가능성을 발견하는 곳.</p>
        <button onClick={() => setPage("diagnosis")}>내 자격 확인하기 →</button>
      </footer>
    </div>
  )
}
