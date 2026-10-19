import { useRef } from "react"
import { BrandLogo } from "../brand/BrandLogo"

export default function LoginDialog() {
  const dialog = useRef<HTMLDialogElement>(null)
  return <>
    <button type="button" className="interface-login-button" onClick={() => dialog.current?.showModal()} aria-haspopup="dialog">로그인</button>
    <dialog ref={dialog} className="interface-login-dialog" aria-labelledby="login-title" aria-describedby="login-description"
      onClick={event => { if (event.target === event.currentTarget) dialog.current?.close() }}>
      <div className="interface-login-content">
        <form method="dialog" className="interface-dialog-close"><button aria-label="로그인 안내 닫기" autoFocus>×</button></form>
        <BrandLogo width={136} />
        <span className="interface-login-status">서비스 준비 중</span>
        <h2 id="login-title">로그인 기능을 준비하고 있어요</h2>
        <p id="login-description">아직 계정 인증이 연결되지 않았어요. 로그인 기능이 제공되면 내 프로필과 진단 기록을 계정으로 관리할 수 있도록 준비할 예정이에요.</p>
        <div className="interface-login-note">현재 자격 진단과 정책 둘러보기는 로그인 없이 이용할 수 있어요.</div>
        <form method="dialog"><button className="interface-primary w-full">확인</button></form>
      </div>
    </dialog>
  </>
}
