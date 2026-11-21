import type { CSSProperties } from "react"
import wave from "../../assets/brand/mascot-wave.webp"
import search from "../../assets/brand/mascot-search.webp"
import thumbs from "../../assets/brand/mascot-thumbs.webp"
import think from "../../assets/brand/mascot-think.webp"
import chat from "../../assets/brand/mascot-chat.webp"
import water from "../../assets/brand/mascot-water.webp"
import fly from "../../assets/brand/mascot-fly.webp"
import jump from "../../assets/brand/mascot-jump.webp"
import "./mascot.css"

export type MascotPose = "wave" | "search" | "thumbs" | "think" | "chat" | "water" | "fly" | "jump"

const ASSETS: Record<MascotPose, { src: string; w: number; h: number }> = {
  wave: { src: wave, w: 398, h: 520 },
  search: { src: search, w: 359, h: 520 },
  thumbs: { src: thumbs, w: 398, h: 520 },
  think: { src: think, w: 349, h: 520 },
  chat: { src: chat, w: 453, h: 520 },
  water: { src: water, w: 378, h: 520 },
  fly: { src: fly, w: 520, h: 361 },
  jump: { src: jump, w: 443, h: 520 },
}

// 장식용 마스코트 일러스트. 읽어주지 않고, 클릭도 받지 않는다.
export default function Mascot({ pose, size, className, float = true, delay = 0, tilt = 0, eager = false }: {
  pose: MascotPose
  size: number
  className?: string
  float?: boolean
  delay?: number
  tilt?: number
  eager?: boolean
}) {
  const a = ASSETS[pose]
  const style = { "--mascot-delay": `${delay}s`, "--mascot-tilt": `${tilt}deg` } as CSSProperties
  const priority = eager ? { fetchPriority: "high" as const } : {}
  return <img
    className={`mascot${float ? " mascot-float" : ""}${className ? ` ${className}` : ""}`}
    src={a.src} alt="" aria-hidden="true" draggable={false}
    loading={eager ? "eager" : "lazy"} decoding="async" {...priority}
    width={size} height={Math.round(size * a.h / a.w)} style={style} />
}
