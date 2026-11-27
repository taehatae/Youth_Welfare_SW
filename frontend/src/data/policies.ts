import type { Policy } from '../types/policy'

export const POLICIES: Policy[] = [
  {
    id: '1', name: '청년 월세 지원', emoji: '🏠',
    desc: '독립 거주 청년에게 월세 비용을 지원하여 주거 부담을 완화합니다.',
    benefit: '월 최대 20만원', period: '2026.03 ~ 2026.12', target: '만 19~34세 무주택 청년',
    region: '서울', category: '주거', status: 'potential',
    conditions: [
      { label: '연령', requirement: '만 19~34세', userValue: '27세', result: 'eligible' },
      { label: '거주지역', requirement: '서울특별시', userValue: '서울', result: 'eligible' },
      { label: '소득', requirement: '중위소득 150% 이하', userValue: '기준 초과', result: 'ineligible' },
      { label: '무주택', requirement: '무주택자', userValue: '무주택', result: 'eligible' },
    ],
    source: '서울시 주거정책과', updated: '2026.09.01',
  },
  {
    id: '2', name: '청년 내일채움공제', emoji: '💼',
    desc: '중소기업 취업 청년이 2년 근속 시 목돈 마련을 지원합니다.',
    benefit: '최대 1,200만원', period: '상시 모집', target: '만 15~34세 중소기업 취업 청년',
    region: '전국', category: '취업', status: 'eligible',
    conditions: [
      { label: '연령', requirement: '만 15~34세', userValue: '27세', result: 'eligible' },
      { label: '취업상태', requirement: '중소기업 재직자', userValue: '중소기업 재직', result: 'eligible' },
      { label: '소득', requirement: '월 300만원 이하', userValue: '280만원', result: 'eligible' },
      { label: '가입기간', requirement: '2년 이상 근속 의향', userValue: '해당', result: 'eligible' },
    ],
    source: '고용노동부', updated: '2026.08.15',
  },
  {
    id: '3', name: '청년 전세임대', emoji: '🔑',
    desc: '한국토지주택공사가 전세 주택을 대신 임차해 저렴하게 제공합니다.',
    benefit: '보증금 최대 1.2억', period: '2026.04 ~ 2026.11', target: '만 19~39세 무주택 청년',
    region: '전국', category: '주거', status: 'ineligible',
    conditions: [
      { label: '연령', requirement: '만 19~39세', userValue: '27세', result: 'eligible' },
      { label: '무주택', requirement: '무주택자', userValue: '무주택', result: 'eligible' },
      { label: '소득', requirement: '중위소득 100% 이하', userValue: '기준 초과', result: 'ineligible' },
      { label: '자산', requirement: '총 자산 3.6억 이하', userValue: '기준 초과', result: 'ineligible' },
    ],
    source: '한국토지주택공사(LH)', updated: '2026.09.10',
  },
  {
    id: '4', name: '청년 도약 계좌', emoji: '🚀',
    desc: '월 70만원 한도 저축 시 정부 기여금과 이자 지원으로 5년 후 목돈 마련.',
    benefit: '최대 5,000만원', period: '2026.01 ~ 2026.12', target: '만 19~34세 개인 소득자',
    region: '전국', category: '금융', status: 'eligible',
    conditions: [
      { label: '연령', requirement: '만 19~34세', userValue: '27세', result: 'eligible' },
      { label: '소득', requirement: '개인소득 7,500만원 이하', userValue: '해당', result: 'eligible' },
      { label: '가구소득', requirement: '중위소득 180% 이하', userValue: '해당', result: 'eligible' },
      { label: '기존 계좌', requirement: '청년희망적금 미보유', userValue: '미보유', result: 'eligible' },
    ],
    source: '금융위원회', updated: '2026.07.20',
  },
  {
    id: '5', name: '국민취업지원제도', emoji: '📋',
    desc: '취업이 어려운 청년에게 취업 지원 서비스와 구직촉진수당을 지원합니다.',
    benefit: '월 50만원 × 6개월', period: '상시 신청', target: '만 15~69세 구직자',
    region: '전국', category: '취업', status: 'unknown',
    conditions: [
      { label: '연령', requirement: '만 15~69세', userValue: '27세', result: 'eligible' },
      { label: '취업상태', requirement: '미취업자 또는 단기근로자', userValue: '확인 필요', result: 'potential' },
      { label: '소득', requirement: '중위소득 60% 이하', userValue: '확인 필요', result: 'potential' },
      { label: '재산', requirement: '재산 4억 이하', userValue: '확인 필요', result: 'potential' },
    ],
    source: '고용노동부', updated: '2026.09.05',
  },
  {
    id: '6', name: '청년 마음건강 지원', emoji: '💚',
    desc: '청년의 심리 건강 회복을 위한 상담 서비스를 바우처로 지원합니다.',
    benefit: '최대 100만원 상담권', period: '2026.02 ~ 2026.12', target: '만 19~34세 청년',
    region: '전국', category: '생활', status: 'eligible',
    conditions: [
      { label: '연령', requirement: '만 19~34세', userValue: '27세', result: 'eligible' },
      { label: '거주지', requirement: '국내 거주자', userValue: '해당', result: 'eligible' },
      { label: '소득', requirement: '소득 무관', userValue: '해당', result: 'eligible' },
      { label: '신청 이력', requirement: '최근 1년 미수혜자', userValue: '해당', result: 'eligible' },
    ],
    source: '보건복지부', updated: '2026.08.30',
  },
]

export const CATEGORIES = ['전체', '주거', '취업', '금융', '생활', '교육', '자산']
