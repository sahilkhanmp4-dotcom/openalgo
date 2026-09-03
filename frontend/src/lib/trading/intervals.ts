/**
 * Interval-token helpers for the trading terminal: how far back to fetch history
 * per timeframe, the bucket size for live candle aggregation, and grouping the
 * broker's supported intervals for the timeframe dropdown.
 */

/** History lookback (days) for an interval token — optimized for 1-second instant chart rendering. */
export function lookbackDays(interval: string): number {
  const m = /^(\d+)([smh])$/.exec(interval)
  if (m) {
    const n = Number(m[1])
    if (m[2] === 's') return 2
    if (m[2] === 'm') return n <= 1 ? 3 : n <= 5 ? 10 : n <= 15 ? 30 : 60
    return 180 // hours (~6 months)
  }
  if (interval === 'D') return 365 // 1 year
  if (interval === 'W') return 3 * 365
  if (interval === 'M') return 5 * 365
  return 30
}


/** Interval token → seconds for the live CandleBuilder; null for D/W/M (no intraday aggregation). */
export function intervalSeconds(interval: string): number | null {
  const m = /^(\d+)([smh])$/.exec(interval)
  if (!m) return null
  const n = Number(m[1])
  return m[2] === 's' ? n : m[2] === 'm' ? n * 60 : n * 3600
}

export interface IntervalData {
  seconds?: string[]
  minutes?: string[]
  hours?: string[]
  days?: string[]
  weeks?: string[]
  months?: string[]
}

export interface IntervalGroup {
  label: string
  items: string[]
}

/** Broker interval payload → ordered, non-empty groups for the timeframe menu. */
export function intervalGroups(data: IntervalData): IntervalGroup[] {
  const order: [string, string[] | undefined][] = [
    ['seconds', data.seconds],
    ['minutes', data.minutes],
    ['hours', data.hours],
    ['days', data.days],
    ['weeks', data.weeks],
    ['months', data.months],
  ]
  return order
    .filter(([, arr]) => arr?.length)
    .map(([label, arr]) => ({ label, items: arr as string[] }))
}

/**
 * Pick the interval to show on load: the saved one if the broker still supports
 * it, else 5m, else the first minute interval, else whatever exists.
 */
export function pickInterval(groups: IntervalGroup[], saved: string | null): string {
  const all = groups.flatMap((g) => g.items)
  if (saved && all.includes(saved)) return saved
  if (all.includes('5m')) return '5m'
  const minutes = groups.find((g) => g.label === 'minutes')
  return minutes?.items[0] ?? all[0] ?? 'D'
}
