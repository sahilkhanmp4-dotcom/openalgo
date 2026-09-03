import { Search, Trash2, ListFilter, ChevronRight, ChevronLeft, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Input } from '@/components/ui/input'
import { useMarketData } from '@/hooks/useMarketData'
import type { SearchRow, TradingTerminal } from '@/lib/trading/terminal'
import { cn } from '@/lib/utils'

const WATCHLIST_STORAGE_KEY = 'oa-trading-watchlist'

const DEFAULT_WATCHLIST: SearchRow[] = [
  { symbol: 'NIFTY', exchange: 'NSE_INDEX', description: 'Nifty 50 Index' },
  { symbol: 'BANKNIFTY', exchange: 'NSE_INDEX', description: 'Nifty Bank Index' },
  { symbol: 'RELIANCE', exchange: 'NSE', description: 'Reliance Industries Ltd' },
  { symbol: 'HDFCBANK', exchange: 'NSE', description: 'HDFC Bank Ltd' },
  { symbol: 'TATAMOTORS', exchange: 'NSE', description: 'Tata Motors Ltd' },
]

function readSavedWatchlist(): SearchRow[] {
  try {
    const raw = localStorage.getItem(WATCHLIST_STORAGE_KEY)
    if (!raw) return DEFAULT_WATCHLIST
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) && parsed.length ? parsed : DEFAULT_WATCHLIST
  } catch {
    return DEFAULT_WATCHLIST
  }
}

interface Props {
  activeTerminal: TradingTerminal | null
  searchFn: (q: string, ex?: string, limit?: number) => Promise<SearchRow[]>
  open: boolean
  onToggle: () => void
}

export function WatchlistPanel({ activeTerminal, searchFn, open, onToggle }: Props) {
  const [items, setItems] = useState<SearchRow[]>(readSavedWatchlist)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchRow[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const searchContainerRef = useRef<HTMLDivElement>(null)

  // Save watchlist on change
  useEffect(() => {
    try {
      localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(items))
    } catch {
      /* ignore */
    }
  }, [items])

  // Live price subscription for watchlist symbols
  const subscribedSymbols = items.map((item) => ({
    symbol: String(item.symbol),
    exchange: String(item.exchange),
  }))

  const { data: liveData } = useMarketData({
    symbols: subscribedSymbols,
    mode: 'LTP',
    enabled: open && items.length > 0,
    autoReconnect: true,
  })

  // Debounced search query against Master Contract API
  useEffect(() => {
    const trimmed = query.trim()
    if (!trimmed) {
      setResults([])
      setDropdownOpen(false)
      return
    }

    let cancel = false
    setIsSearching(true)

    const timer = setTimeout(async () => {
      try {
        const rows = await searchFn(trimmed, undefined, 20)
        if (!cancel) {
          setResults(rows || [])
          setDropdownOpen(true)
        }
      } catch {
        if (!cancel) setResults([])
      } finally {
        if (!cancel) setIsSearching(false)
      }
    }, 200)

    return () => {
      cancel = true
      clearTimeout(timer)
    }
  }, [query, searchFn])

  // Close search dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const addItem = (row: SearchRow) => {
    setItems((prev) => {
      const exists = prev.some(
        (it) => it.symbol === row.symbol && it.exchange === row.exchange
      )
      if (exists) return prev
      return [row, ...prev]
    })
    setQuery('')
    setDropdownOpen(false)
  }

  const removeItem = (e: React.MouseEvent, index: number) => {
    e.stopPropagation()
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  const selectSymbol = (row: SearchRow) => {
    if (activeTerminal) {
      void activeTerminal.loadSymbol(row)
    }
  }

  return (
    <aside
      className={cn(
        'relative flex h-full flex-col border-l bg-card transition-all duration-200 ease-in-out',
        open ? 'w-64 min-w-[16rem]' : 'w-10 min-w-[2.5rem]'
      )}
    >
      {/* Sidebar Header / Toggle button */}
      <div className="flex h-11 items-center justify-between border-b px-2">
        <button
          type="button"
          onClick={onToggle}
          title={open ? 'Collapse Watchlist' : 'Expand Watchlist'}
          className="flex h-8 w-full items-center justify-between rounded-md px-1.5 text-xs font-semibold text-foreground hover:bg-accent"
        >
          <div className="flex items-center gap-1.5 overflow-hidden">
            <ListFilter className="h-4 w-4 shrink-0 text-primary" />
            {open && <span className="truncate">Watchlist</span>}
          </div>
          {open ? (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronLeft className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
      </div>

      {open && (
        <>
          {/* Keyword Search Input for Master Contract */}
          <div ref={searchContainerRef} className="relative border-b p-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search symbol / contract..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => query.trim() && setDropdownOpen(true)}
                className="h-8 pl-8 pr-7 text-xs font-mono"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            {/* Matching Master Contract Dropdown */}
            {dropdownOpen && (
              <div className="absolute left-2 right-2 top-11 z-50 max-h-64 overflow-y-auto rounded-md border bg-popover p-1 shadow-lg">
                {isSearching ? (
                  <div className="py-3 text-center text-xs text-muted-foreground">Searching contracts…</div>
                ) : results.length > 0 ? (
                  results.map((row, idx) => (
                    <button
                      type="button"
                      key={`${row.exchange}:${row.symbol}-${idx}`}
                      onClick={() => addItem(row)}
                      className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs hover:bg-accent hover:text-accent-foreground"
                    >
                      <div className="min-w-0 pr-2">
                        <div className="font-semibold text-foreground">{row.symbol}</div>
                        {row.description && (
                          <div className="truncate text-[10px] text-muted-foreground">
                            {row.description}
                          </div>
                        )}
                      </div>
                      <span className="shrink-0 rounded bg-muted px-1 py-0.5 text-[9px] font-medium text-muted-foreground">
                        {row.exchange}
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="py-3 text-center text-xs text-muted-foreground">No matching scrips found</div>
                )}
              </div>
            )}
          </div>

          {/* Watchlist Scrips List */}
          <div className="flex-1 overflow-y-auto p-1">
            {items.length === 0 ? (
              <div className="p-4 text-center text-xs text-muted-foreground">
                Watchlist is empty. Search above to add scrips.
              </div>
            ) : (
              <div className="space-y-0.5">
                {items.map((row, idx) => {
                  const key = `${row.exchange}:${row.symbol}`
                  const tick = liveData.get(key)?.data
                  const ltp = tick?.ltp
                  const change = tick?.change
                  const changePercent = tick?.change_percent

                  const isUp = changePercent != null ? changePercent >= 0 : true

                  return (
                    <div
                      key={`${row.exchange}:${row.symbol}-${idx}`}
                      onClick={() => selectSymbol(row)}
                      className="group flex cursor-pointer items-center justify-between rounded-md px-2 py-1.5 transition-colors hover:bg-accent/60"
                    >
                      {/* Left: Symbol & Exchange */}
                      <div className="min-w-0 flex-1 pr-2">
                        <div className="flex items-center gap-1.5">
                          <span className="truncate text-xs font-semibold text-foreground">
                            {row.symbol}
                          </span>
                          <span className="rounded bg-muted px-1 py-0.2 text-[9px] font-medium text-muted-foreground">
                            {row.exchange}
                          </span>
                        </div>
                        {row.description && (
                          <div className="truncate text-[10px] text-muted-foreground">
                            {row.description}
                          </div>
                        )}
                      </div>

                      {/* Right: LTP & Change */}
                      <div className="flex items-center gap-1.5 text-right">
                        <div>
                          <div className="font-mono text-xs font-semibold text-foreground">
                            {ltp != null ? ltp.toFixed(2) : '—'}
                          </div>
                          {changePercent != null && (
                            <div
                              className={cn(
                                'flex items-center justify-end text-[10px] font-medium',
                                isUp ? 'text-emerald-500' : 'text-rose-500'
                              )}
                            >
                              {isUp ? '+' : ''}
                              {changePercent.toFixed(2)}%
                            </div>
                          )}
                        </div>

                        {/* Remove Action */}
                        <button
                          type="button"
                          onClick={(e) => removeItem(e, idx)}
                          title="Remove from watchlist"
                          className="opacity-0 transition-opacity group-hover:opacity-100 hover:text-rose-500"
                        >
                          <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}
    </aside>
  )
}
