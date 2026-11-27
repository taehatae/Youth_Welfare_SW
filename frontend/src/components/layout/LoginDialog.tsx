import { useEffect, useRef, useState, type FormEvent } from "react"
import { BrandLogo } from "../brand/BrandLogo"
import { signIn, signUp, type Account } from "../../services/welfareApi"

export default function LoginDialog({ open, onClose, onSuccess }: {
  open: boolean
  onClose: () => void
  onSuccess: (account: Account) => Promise<void>
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [signup, setSignup] = useState(false)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [confirmation, setConfirmation] = useState("")
  const [name, setName] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const pending = useRef(false)
  useEffect(() => {
    if (open) dialog.current?.showModal()
    else { dialog.current?.close(); setPassword(""); setConfirmation(""); setError("") }
  }, [open])
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (pending.current) return
    setError("")
    if (signup && password !== confirmation) { setError("비밀번호 확인이 일치하지 않아요."); return }
    pending.current = true
    setBusy(true)
    try {
      const account = signup ? await signUp(username.trim(), password, name.trim()) : await signIn(username.trim(), password)
      setPassword(""); setConfirmation("")
      await onSuccess(account)
      onClose()
    } catch (e) { setError(e instanceof Error ? e.message : "로그인하지 못했어요.") }
    finally { pending.current = false; setBusy(false) }
  }
  return <dialog ref={dialog} className="interface-login-dialog" aria-labelledby="login-title"
    onCancel={event => { event.preventDefault(); if (!busy) onClose() }}
    onClick={event => { if (event.target === event.currentTarget && !busy) onClose() }}>
    <div className="interface-login-content">
      <button className="auth-close" aria-label="로그인 창 닫기" disabled={busy} onClick={onClose}>×</button>
      <BrandLogo width={136} />
      <span className="interface-login-status">나의 조건, 나의 계정에</span>
      <h2 id="login-title">{signup ? "자격있청 시작하기" : "다시 만나 반가워요"}</h2>
      <p>프로필과 진단 결과를 저장하고, 나의 현황에서 이어서 확인하세요.</p>
      <form className="auth-form" onSubmit={submit}>
        {signup && <label>이름 또는 닉네임<input autoComplete="nickname" value={name} onChange={e => setName(e.target.value)} required maxLength={40} disabled={busy} /></label>}
        <label>아이디<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required pattern="[a-zA-Z0-9_]{3,30}" minLength={3} maxLength={30} disabled={busy} aria-describedby="username-hint" /></label>
        <small id="username-hint">영문·숫자·밑줄 3~30자 (대소문자 구분 없음)</small>
        <label>비밀번호<input type="password" autoComplete={signup ? "new-password" : "current-password"} value={password} onChange={e => setPassword(e.target.value)} required minLength={10} maxLength={128} disabled={busy} /></label>
        <small>10~128자</small>
        {signup && <label>비밀번호 확인<input type="password" autoComplete="new-password" value={confirmation} onChange={e => setConfirmation(e.target.value)} required minLength={10} maxLength={128} disabled={busy} /></label>}
        {error && <p role="alert" className="auth-error">{error}</p>}
        <button className="interface-primary w-full" disabled={busy}>{busy ? "처리 중…" : signup ? "가입하고 시작하기" : "로그인"}</button>
      </form>
      <button className="auth-switch" disabled={busy} onClick={() => { setSignup(!signup); setError(""); setPassword(""); setConfirmation("") }}>
        {signup ? "이미 계정이 있어요 · 로그인" : "처음 방문했어요 · 회원가입"}
      </button>
    </div>
  </dialog>
}
