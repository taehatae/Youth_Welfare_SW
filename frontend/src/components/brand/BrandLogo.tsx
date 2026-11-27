import wordmark from "../../assets/brand/youth-wordmark.png"
import mascotHead from "../../assets/brand/mascot-avatar.webp"
import "./brand-logo.css"

/** 워드마크 옆에 마스코트 얼굴을 함께 보여준다(mascot=false면 워드마크만). */
export function BrandLogo({ width = 128, mascot = true }: { width?: number; mascot?: boolean }) {
  const head = Math.round(width * 0.36)
  return (
    <span className="brand-logo">
      <img
        src={wordmark}
        alt="자격있청 For Youth"
        width={width}
        height={width / 2}
        className="block shrink-0 object-contain"
        draggable={false}
      />
      {mascot && (
        <img
          src={mascotHead}
          alt=""
          aria-hidden="true"
          width={head}
          height={head}
          className="brand-logo-mascot"
          draggable={false}
        />
      )}
    </span>
  )
}
