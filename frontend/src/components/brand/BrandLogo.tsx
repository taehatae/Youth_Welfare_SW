import wordmark from "../../assets/brand/youth-wordmark.png"

export function BrandLogo({ width = 128 }: { width?: number }) {
  return (
    <img
      src={wordmark}
      alt="자격있청 For Youth"
      width={width}
      height={width / 2}
      className="block shrink-0 object-contain"
      draggable={false}
    />
  )
}
