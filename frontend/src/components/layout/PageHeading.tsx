import type { ReactNode } from "react"

export default function PageHeading({ eyebrow, title, description, children, action }: {
  eyebrow: string; title: string; description: string; children?: ReactNode; action?: ReactNode
}) {
  return <header className="interface-heading">
    <div className="interface-heading-top">
      <div>
        <p className="interface-eyebrow"><span aria-hidden="true">✦</span> {eyebrow}</p>
        <h1>{title}</h1>
        <p className="interface-description">{description}</p>
      </div>
      {action && <div className="interface-heading-action">{action}</div>}
    </div>
    {children && <div className="interface-heading-content">{children}</div>}
  </header>
}
