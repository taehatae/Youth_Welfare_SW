import { useState } from 'react'
import type { Page } from '../../types/page'
import type { EmploymentStatus, UserProfileInput, YesNoUnknown } from '../../types/welfareApi'

const STEPS = ['기본정보', '거주정보', '소득정보', '주거정보', '재산/취업', '추가 자격']
const EMPLOYMENT_STATUS: Record<string, EmploymentStatus> = {
  '대기업 재직': 'EMPLOYED', '중소기업 재직': 'EMPLOYED_SME', '공공기관 재직': 'EMPLOYED',
  '자영업': 'SELF_EMPLOYED', '프리랜서': 'FREELANCER', '구직 중': 'UNEMPLOYED',
  '학생': 'STUDENT', '기타': 'OTHER',
}

export default function DiagnosisPage({ setPage, onComplete }: { setPage: (p: Page) => void; onComplete: (profile: UserProfileInput) => Promise<void> }) {
  const [step, setStep] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ age: '', gender: '', region: '', district: '', income: '', incomeType: '', housing: '', ownsHome: '', householdSize: '', asset: '', employment: '', disability: '', student: '', maritalStatus: '', childrenCount: '', qualifications: '' })
  const update = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const canNext = [Number(form.age) >= 19 && Number(form.age) <= 34, form.region !== '' && form.district.trim() !== '', Number(form.income) >= 0 && form.income !== '', form.housing !== '', form.employment !== '', true][step] ?? false
  const continueDiagnosis = async () => {
    if (step < STEPS.length - 1) {
      setStep(current => current + 1)
      return
    }
    if (!canNext || submitting) return
    setSubmitting(true)
    setError('')
    try {
      await onComplete({
        age: Number(form.age),
        region: `${form.region} ${form.district.trim()}`,
        income_level: Math.round(Number(form.income) * 10_000),
        employment_status: EMPLOYMENT_STATUS[form.employment],
        eligibility_conditions: {
          gender: form.gender === '남성' ? 'MALE' : form.gender === '여성' ? 'FEMALE' : 'UNKNOWN',
          household_size: form.householdSize ? Number(form.householdSize) : null,
          income_type: ({ '근로소득': 'LABOR', '사업소득': 'BUSINESS', '프리랜서': 'FREELANCE', '무소득': 'NONE' } as Record<string, 'LABOR' | 'BUSINESS' | 'FREELANCE' | 'NONE'>)[form.incomeType] ?? 'UNKNOWN',
          asset_range: form.asset || null,
          housing_type: form.housing || null,
          owns_home: form.ownsHome === 'yes' ? true : form.ownsHome === 'no' ? false : null,
          disability_status: (form.disability || 'UNKNOWN') as YesNoUnknown,
          student_status: (form.student || 'UNKNOWN') as YesNoUnknown,
          marital_status: (form.maritalStatus || 'UNKNOWN') as 'SINGLE' | 'MARRIED' | 'DIVORCED' | 'WIDOWED' | 'UNKNOWN',
          children_count: form.childrenCount === '' ? null : Number(form.childrenCount),
          qualifications: form.qualifications.split(',').map(value => value.trim()).filter(Boolean),
          additional_conditions: {},
        },
      })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '진단을 완료하지 못했습니다. 잠시 후 다시 시도해주세요.')
      setSubmitting(false)
    }
  }

  const stepContent = [
    <div key="0" className="space-y-6">
      <div>
        <label className="block text-sm font-black text-slate-900 mb-1">나이 <span className="text-blue-600">*</span></label>
        <p className="text-xs text-slate-500 mb-3">만 나이 기준 · 청년 정책 대부분은 만 19~34세가 대상이에요</p>
        <input type="number" value={form.age} onChange={e => update('age', e.target.value)} placeholder="예: 27"
          className="w-full border-2 border-slate-200 focus:border-blue-500 rounded-xl px-4 py-3.5 text-sm font-bold focus:outline-none transition-colors" />
        {form.age && (
          <div className={`mt-2 inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-black ${parseInt(form.age) >= 19 && parseInt(form.age) <= 34 ? 'bg-emerald-100 text-emerald-700' : 'bg-orange-100 text-orange-700'}`}>
            {parseInt(form.age) >= 19 && parseInt(form.age) <= 34 ? '✓ 청년 연령 충족' : '✕ 일부 정책 제한 가능'}
          </div>
        )}
      </div>
      <div>
        <label className="block text-sm font-black text-slate-900 mb-3">성별</label>
        <div className="flex gap-3">
          {['남성', '여성', '선택 안 함'].map(v => (
            <button key={v} onClick={() => update('gender', v)}
              className={`flex-1 py-3.5 rounded-xl border-2 text-sm font-black transition-all ${form.gender === v ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'}`}>
              {v}
            </button>
          ))}
        </div>
      </div>
    </div>,

    <div key="1" className="space-y-5">
      <div>
        <label className="block text-sm font-black text-slate-900 mb-1">거주 지역 <span className="text-blue-600">*</span></label>
        <p className="text-xs text-slate-500 mb-3">주민등록상 주소지 기준 · 일부 정책은 특정 지역에서만 지원돼요</p>
        <select value={form.region} onChange={e => update('region', e.target.value)}
          className="w-full border-2 border-slate-200 focus:border-blue-500 rounded-xl px-4 py-3.5 text-sm font-bold focus:outline-none bg-white transition-colors">
          <option value="">시/도 선택</option>
          {['서울특별시','부산광역시','대구광역시','인천광역시','광주광역시','대전광역시','울산광역시','세종특별자치시','경기도','강원도','충청북도','충청남도','전라북도','전라남도','경상북도','경상남도','제주특별자치도'].map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <label className="mt-4 block text-sm font-black text-slate-900 mb-2">시/군/구 <span className="text-blue-600">*</span></label>
        <input value={form.district} onChange={e => update('district', e.target.value)} placeholder="예: 관악구"
          className="w-full border-2 border-slate-200 focus:border-blue-500 rounded-xl px-4 py-3.5 text-sm font-bold focus:outline-none transition-colors" />
        {form.region && <div className="mt-2 inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-black bg-emerald-100 text-emerald-700">✓ {form.region} 입력 완료</div>}
      </div>
    </div>,

    <div key="2" className="space-y-5">
      <div>
        <label className="block text-sm font-black text-slate-900 mb-1">월 소득 <span className="text-blue-600">*</span></label>
        <p className="text-xs text-slate-500 mb-3">세전 월 소득 기준 · 근로소득, 사업소득 등 합산</p>
        <div className="relative">
          <input type="number" value={form.income} onChange={e => update('income', e.target.value)} placeholder="예: 280"
            className="w-full border-2 border-slate-200 focus:border-blue-500 rounded-xl px-4 py-3.5 pr-12 text-sm font-bold focus:outline-none transition-colors" />
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-sm">만원</span>
        </div>
        {form.income && (
          <div className="mt-3 bg-blue-50 border border-blue-100 rounded-xl p-3 text-xs">
            <div className="font-black text-blue-700 mb-1.5">소득 기준 참고 (1인 가구)</div>
            {[['중위소득 100%', '약 228만원'], ['중위소득 150%', '약 342만원'], ['중위소득 180%', '약 411만원']].map(([l, v]) => (
              <div key={l} className={`flex justify-between py-0.5 ${parseInt(form.income) * 10000 < parseInt(v.replace(/[^0-9]/g,'')) * 10000 ? 'text-emerald-700 font-bold' : 'text-slate-500'}`}>
                <span>{l}</span><span>{v}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div>
        <label className="block text-sm font-black text-slate-900 mb-3">소득 유형</label>
        <div className="grid grid-cols-2 gap-2">
          {['근로소득', '사업소득', '프리랜서', '무소득'].map(v => (
            <button key={v} onClick={() => update('incomeType', v)}
              className={`py-3.5 rounded-xl border-2 text-sm font-black transition-all ${form.incomeType === v ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'}`}>
              {v}
            </button>
          ))}
        </div>
      </div>
    </div>,

    <div key="3" className="space-y-5">
      <div>
        <label className="block text-sm font-black text-slate-900 mb-1">주거 형태 <span className="text-blue-600">*</span></label>
        <p className="text-xs text-slate-500 mb-3">현재 거주하는 주택의 점유 형태</p>
        <div className="grid grid-cols-2 gap-2">
          {['자가', '전세', '월세', '보증금 있는 월세', '사글세/방세', '기타'].map(v => (
            <button key={v} onClick={() => update('housing', v)}
              className={`py-3.5 rounded-xl border-2 text-sm font-black transition-all ${form.housing === v ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'}`}>
              {v}
            </button>
          ))}
        </div>
        {form.housing && (
          <div className={`mt-2 inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-black ${form.housing !== '자가' ? 'bg-emerald-100 text-emerald-700' : 'bg-orange-100 text-orange-700'}`}>
            {form.housing !== '자가' ? '✓ 무주택 조건 충족 가능' : '△ 주택 소유자 — 일부 정책 제한'}
          </div>
        )}
      </div>
      <div>
        <label className="block text-sm font-black text-slate-900 mb-3">주택 보유 여부</label>
        <div className="grid grid-cols-3 gap-2">
          {[['yes', '보유'], ['no', '미보유'], ['', '미확인']].map(([value, label]) => (
            <button key={label} type="button" onClick={() => update('ownsHome', value)} aria-pressed={form.ownsHome === value}
              className={`py-3 rounded-xl border-2 text-sm font-black transition-all ${form.ownsHome === value ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'}`}>
              {label}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-500">주거 형태와 주택 소유 여부는 정책에 따라 별도로 판단될 수 있어요.</p>
      </div>
      <div>
        <label className="block text-sm font-black text-slate-900 mb-3">가구원 수</label>
        <select value={form.householdSize} onChange={e => update('householdSize', e.target.value)}
          className="w-full border-2 border-slate-200 focus:border-blue-500 rounded-xl px-4 py-3.5 text-sm font-bold focus:outline-none bg-white">
          <option value="">선택 안 함</option>
          {Array.from({ length: 10 }, (_, index) => index + 1).map(value => <option key={value} value={value}>{value}인 가구</option>)}
        </select>
      </div>
    </div>,

    <div key="4" className="space-y-5">
      <div>
        <label className="block text-sm font-black text-slate-900 mb-1">총 자산</label>
        <p className="text-xs text-slate-500 mb-3">예금, 적금, 부동산 등 합산 (개략)</p>
        <select value={form.asset} onChange={e => update('asset', e.target.value)}
          className="w-full border-2 border-slate-200 focus:border-blue-500 rounded-xl px-4 py-3.5 text-sm font-bold focus:outline-none bg-white">
          <option value="">선택해주세요</option>
          <option>1억 미만</option><option>1~2억</option><option>2~3억</option><option>3~5억</option><option>5억 이상</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-black text-slate-900 mb-3">취업 상태 <span className="text-blue-600">*</span></label>
        <div className="grid grid-cols-2 gap-2">
          {['대기업 재직', '중소기업 재직', '공공기관 재직', '자영업', '프리랜서', '구직 중', '학생', '기타'].map(v => (
            <button key={v} onClick={() => update('employment', v)}
              className={`py-3.5 rounded-xl border-2 text-sm font-black transition-all ${form.employment === v ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'}`}>
              {v}
            </button>
          ))}
        </div>
      </div>
    </div>,

    <div key="5" className="space-y-6">
      <p className="rounded-xl bg-blue-50 p-4 text-sm leading-relaxed text-blue-900">아래 항목은 선택 입력이에요. 모르는 항목은 미확인으로 두어도 됩니다. 입력한 값은 자격 조건 비교를 위해 백엔드로 전송됩니다.</p>
      {([
        ['disability', '장애 여부'],
        ['student', '학생 여부'],
      ] as const).map(([key, label]) => (
        <div key={key}>
          <label className="mb-2 block text-sm font-black text-slate-900">{label}</label>
          <div className="grid grid-cols-3 gap-2">
            {([['YES', '해당'], ['NO', '해당 없음'], ['', '미확인']] as const).map(([value, text]) => (
              <button key={text} type="button" onClick={() => update(key, value)} aria-pressed={form[key] === value}
                className={`rounded-xl border-2 py-3 text-sm font-black ${form[key] === value ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white text-slate-600'}`}>
                {text}
              </button>
            ))}
          </div>
        </div>
      ))}
      <div>
        <label htmlFor="marital-status" className="mb-2 block text-sm font-black text-slate-900">혼인 상태</label>
        <select id="marital-status" value={form.maritalStatus} onChange={e => update('maritalStatus', e.target.value)} className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3.5 text-sm font-bold">
          <option value="">미확인</option><option value="SINGLE">미혼</option><option value="MARRIED">기혼</option><option value="DIVORCED">이혼</option><option value="WIDOWED">사별</option>
        </select>
      </div>
      <div>
        <label htmlFor="children-count" className="mb-2 block text-sm font-black text-slate-900">자녀 수</label>
        <input id="children-count" type="number" min="0" max="20" value={form.childrenCount} onChange={e => update('childrenCount', e.target.value)} placeholder="모르면 비워두세요" className="w-full rounded-xl border-2 border-slate-200 px-4 py-3.5 text-sm font-bold" />
      </div>
      <div>
        <label htmlFor="qualifications" className="mb-2 block text-sm font-black text-slate-900">보유 자격·면허</label>
        <input id="qualifications" value={form.qualifications} onChange={e => update('qualifications', e.target.value)} placeholder="예: 사회복지사 2급, 운전면허 (쉼표로 구분)" className="w-full rounded-xl border-2 border-slate-200 px-4 py-3.5 text-sm font-bold" />
      </div>
    </div>,
  ]

  return (
    <div className="pb-20 md:pb-0">
      {/* Progress header */}
      <div className="bg-slate-900 border-b-2 border-slate-800 py-6 px-4 sm:px-6">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center justify-between mb-4">
            <div className="text-emerald-400 text-xs font-black tracking-widest">자격 진단</div>
            <div className="text-slate-400 text-xs font-black">{step + 1} / {STEPS.length}</div>
          </div>
          <div className="flex gap-1.5 mb-3">
            {STEPS.map((_, i) => (
              <div key={i} className={`flex-1 h-1.5 rounded-full transition-all ${i <= step ? 'bg-blue-500' : 'bg-slate-700'}`} />
            ))}
          </div>
          <div className="flex justify-between">
            {STEPS.map((s, i) => (
              <span key={i} className={`text-[10px] font-black ${i <= step ? 'text-blue-400' : 'text-slate-600'}`}>{s}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
        {/* Big step number */}
        <div className="flex items-center gap-4 mb-8">
          <div className="w-14 h-14 bg-blue-600 text-white rounded-2xl flex items-center justify-center font-black text-2xl border-2 border-slate-900 shadow-[3px_3px_0px_#0A0F1E] flex-shrink-0">
            {String(step + 1).padStart(2, '0')}
          </div>
          <div>
            <div className="font-black text-slate-900 text-xl">{STEPS[step]}</div>
            <div className="text-slate-500 text-xs mt-0.5">정확한 정보를 입력할수록 진단이 더 정확해요</div>
          </div>
        </div>

        {/* Form content */}
        <div className="bg-white border-2 border-slate-200 rounded-2xl p-6 mb-6">
          {stepContent[step]}
        </div>

        <p className="text-xs text-slate-500 mb-4">입력한 프로필은 맞춤 정책을 조회하기 위해 백엔드로 전송됩니다.</p>
        {error && <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700">{error}</div>}

        {/* Nav buttons */}
        <div className="flex gap-3">
          {step > 0 && (
            <button onClick={() => setStep(s => s - 1)}
              className="px-6 py-4 border-2 border-slate-900 rounded-xl text-slate-900 font-black hover:bg-slate-900 hover:text-white transition-colors">
              ← 이전
            </button>
          )}
          <button
            onClick={continueDiagnosis}
            disabled={!canNext || submitting}
            className={`flex-1 py-4 rounded-xl font-black text-base transition-all border-2 ${
              canNext && !submitting
                ? 'bg-blue-600 text-white border-slate-900 shadow-[3px_3px_0px_#0A0F1E] hover:bg-blue-700'
                : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
            }`}
          >
            {submitting ? '정책을 분석하고 있어요…' : step < STEPS.length - 1 ? '다음 단계 →' : '맞춤 복지 분석하기 →'}
          </button>
        </div>
      </div>
    </div>
  )
}
