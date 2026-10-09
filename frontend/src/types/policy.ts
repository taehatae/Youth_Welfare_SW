export interface Policy {
  id: string
  name: string
  desc: string
  benefit: string
  period: string
  target: string
  region: string
  category: string
  status: 'eligible' | 'potential' | 'ineligible' | 'unknown'
  conditions: Condition[]
  source: string
  updated: string
  emoji: string
}

export interface Condition {
  label: string
  requirement: string
  userValue: string
  result: 'eligible' | 'potential' | 'ineligible'
}
