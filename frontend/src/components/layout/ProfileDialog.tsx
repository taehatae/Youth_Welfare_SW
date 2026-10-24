import { useEffect, useRef, useState, type FormEvent } from "react"
import { viewAccountProfile } from "../../services/welfareApi"
import type { UserProfileInput } from "../../types/welfareApi"
import { profileSummary } from "../../services/profileSummary"

export default function ProfileDialog({ snapshot, editStep, onClose, onEdit, onAuthFailure }: {
  snapshot: "current" | "diagnosis"
  editStep?: number
  onClose: () => void
  onEdit: (profile: UserProfileInput, step?: number) => void
  onAuthFailure: (error: unknown) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const active = useRef(true)
  const pending = useRef(false)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [profile, setProfile] = useState<UserProfileInput | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  useEffect(() => {
    active.current = true
    dialog.current?.showModal()
    return () => { active.current = false }
  }, [])
  useEffect(() => {
    if (!profile) return
    const clear = () => { setProfile(null); setPassword(""); setError("보호를 위해 프로필 조회를 잠갔어요. 다시 본인 확인해주세요.") }
    const timer = window.setTimeout(clear, 120_000)
    const hide = () => { if (document.hidden) clear() }
    document.addEventListener("visibilitychange", hide)
    window.addEventListener("blur", clear)
    return () => { window.clearTimeout(timer); document.removeEventListener("visibilitychange", hide); window.removeEventListener("blur", clear) }
  }, [profile])
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (pending.current) return
    pending.current = true; setBusy(true); setError("")
    try {
      const result = await viewAccountProfile(username.trim(), password, snapshot)
      if (!active.current) return
      setPassword("")
      if (!result) { setError("저장된 프로필이 없어요. 먼저 자격 진단을 진행해주세요."); return }
      if (document.hidden || !document.hasFocus()) { setError("화면으로 돌아왔어요. 다시 본인 확인해주세요."); return }
      if (editStep !== undefined) { onClose(); onEdit(result, editStep) }
      else setProfile(result)
    } catch (error) {
      if (active.current) { onAuthFailure(error); setError(error instanceof Error ? error.message : "본인 확인에 실패했어요.") }
    } finally { if (active.current) { setPassword(""); setBusy(false) }; pending.current = false }
  }
  return <dialog ref={dialog} className="interface-login-dialog profile-view-dialog" aria-labelledby="profile-view-title"
    onCancel={event => { event.preventDefault(); onClose() }}>
    <div className="interface-login-content">
      <button className="auth-close" aria-label="프로필 창 닫기" onClick={onClose}>×</button>
      <h2 id="profile-view-title">{profile ? "저장된 내 프로필" : "프로필 본인 확인"}</h2>
      {profile ? <>
        <p>입력했던 값 그대로예요. 2분이 지나거나 다른 창으로 이동하면 잠겨요.</p>
        <div className="protected-profile-fields">{profileSummary(profile).map(group => <section key={group.title}>
          <h3>{group.title}</h3><dl>{group.items.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
        </section>)}</div>
        <button className="interface-primary" onClick={() => { onClose(); onEdit(profile, 0) }}>이 정보로 수정 후 재진단</button>
      </> : <>
        <p>현재 로그인한 계정의 아이디와 비밀번호를 다시 입력해주세요.</p>
        <form className="auth-form" onSubmit={submit}>
          <label>아이디<input autoComplete="off" required minLength={3} maxLength={30} value={username} onChange={e => setUsername(e.target.value)} disabled={busy} /></label>
          <label>비밀번호<input type="password" autoComplete="off" required minLength={10} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} disabled={busy} /></label>
          {error && <p role="alert" className="auth-error">{error}</p>}
          <button className="interface-primary" disabled={busy}>{busy ? "확인 중…" : editStep !== undefined ? "본인 확인 후 수정" : "본인 확인 후 조회"}</button>
        </form>
      </>}
    </div>
  </dialog>
}
