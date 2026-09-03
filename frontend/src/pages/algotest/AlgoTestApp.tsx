import React, { useState, useEffect, useMemo } from 'react'
import {
  Layers,
  BarChart2,
  Play,
  Zap,
  Activity,
  Sliders,
  Calendar,
  Settings,
  Plus,
  Trash2,
  TrendingUp,
  Shield,
  Clock,
  RotateCcw,
  Sparkles,
  Download,
  Upload,
  Cpu,
  RefreshCw,
  PieChart,
  Save,
  FolderOpen,
  Check,
  FileSpreadsheet,
  TrendingDown,
  Percent,
  SlidersHorizontal,
  Square,
  Pause,
  CheckCircle2,
  Radio,
  Share2,
  Filter,
  CheckCheck
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { showToast } from '@/utils/toast'
import {
  algotestApi,
  deploymentApi,
  type OptionLegConfig,
  type AlgoTestStrategy,
  type BacktestResponseData,
  type AlgoDeployment
} from '@/api/algotest'

export default function AlgoTestApp() {
  const [activeTab, setActiveTab] = useState<
    'builder' | 'backtest' | 'simulator' | 'forward' | 'live' | 'signals' | 'marketplace' | 'analytics'
  >('builder')

  const [strategyId, setStrategyId] = useState<string>('strat_920_straddle')
  const [strategyName, setStrategyName] = useState('9:20 Short Straddle with Trailing SL')
  const [underlying, setUnderlying] = useState<'NIFTY' | 'BANKNIFTY' | 'FINNIFTY' | 'SENSEX'>('NIFTY')
  const [entryTime, setEntryTime] = useState('09:20')
  const [exitTime, setExitTime] = useState('15:15')
  const [strategyType, setStrategyType] = useState<'INTRADAY' | 'BTST' | 'POSITIONAL'>('INTRADAY')
  
  // Overall MTM Risk Controls
  const [overallSLValue, setOverallSLValue] = useState(3000)
  const [overallTargetValue, setOverallTargetValue] = useState(6000)
  const [mtmTrailWhen, setMtmTrailWhen] = useState(2000)
  const [mtmTrailBy, setMtmTrailBy] = useState(1000)

  const [startDate, setStartDate] = useState('2023-01-01')
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0])
  const [isBacktesting, setIsBacktesting] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  // Signals AI state
  const [signalIndicator, setSignalIndicator] = useState<'SUPERTREND' | 'VWAP' | 'EMA_CROSS' | 'PREMIUM_MOMENTUM'>('SUPERTREND')
  const [signalTimeframe, setSignalTimeframe] = useState<'1m' | '3m' | '5m' | '15m'>('5m')
  const [signalParam1, setSignalParam1] = useState(10) // ATR Period or Fast EMA
  const [signalParam2, setSignalParam2] = useState(3) // Multiplier or Slow EMA
  const [signalAction, setSignalAction] = useState<'BUY_CALL_SELL_PUT' | 'BUY_PUT_SELL_CALL' | 'ATM_STRADDLE'>('BUY_CALL_SELL_PUT')

  // Simulator State
  const spotPriceBase = underlying === 'NIFTY' ? 24000 : underlying === 'BANKNIFTY' ? 52000 : 22000
  const [simSpotShift, setSimSpotShift] = useState(0)
  const [simIvShift, setSimIvShift] = useState(0)
  const [simDaysToExpiry, setSimDaysToExpiry] = useState(4)

  // Saved strategies & Live Deployments
  const [savedStrategies, setSavedStrategies] = useState<AlgoTestStrategy[]>([])
  const [deployments, setDeployments] = useState<AlgoDeployment[]>([])

  const [legs, setLegs] = useState<OptionLegConfig[]>([
    {
      id: 'leg_1',
      position_type: 'SELL',
      option_type: 'CE',
      expiry: 'CURRENT_WEEK',
      lots: 1,
      strike_selection: 'ATM',
      sl_type: 'PERCENTAGE',
      sl_value: 25,
      target_type: 'PERCENTAGE',
      target_value: 80,
      trailing_sl: true,
      trail_when: 10,
      trail_by: 5,
      re_entry_type: 'RE_ENTRY_SL',
      momentum_type: 'NONE',
      momentum_value: 0,
    },
    {
      id: 'leg_2',
      position_type: 'SELL',
      option_type: 'PE',
      expiry: 'CURRENT_WEEK',
      lots: 1,
      strike_selection: 'ATM',
      sl_type: 'PERCENTAGE',
      sl_value: 25,
      target_type: 'PERCENTAGE',
      target_value: 80,
      trailing_sl: true,
      trail_when: 10,
      trail_by: 5,
      re_entry_type: 'RE_ENTRY_SL',
      momentum_type: 'NONE',
      momentum_value: 0,
    },
  ])

  const [results, setResults] = useState<BacktestResponseData | null>(null)

  useEffect(() => {
    loadSavedStrategies()
    loadDeployments()
  }, [])

  const loadSavedStrategies = async () => {
    try {
      const data = await algotestApi.getStrategies()
      setSavedStrategies(data)
    } catch (e) {
      console.error('Failed to load strategies:', e)
    }
  }

  const loadDeployments = async () => {
    try {
      const data = await deploymentApi.getDeployments()
      setDeployments(data)
    } catch (e) {
      console.error('Failed to load deployments:', e)
    }
  }

  const handleSaveStrategy = async () => {
    setIsSaving(true)
    try {
      await algotestApi.saveStrategy({
        id: strategyId,
        name: strategyName,
        underlying,
        strategy_type: strategyType,
        entry_time: entryTime,
        exit_time: exitTime,
        overall_sl: overallSLValue,
        overall_target: overallTargetValue,
        mtm_trail_when: mtmTrailWhen,
        mtm_trail_by: mtmTrailBy,
        legs,
      })
      await loadSavedStrategies()
      showToast.success('Strategy saved successfully!')
    } catch (e) {
      showToast.error('Failed to save strategy')
    } finally {
      setIsSaving(false)
    }
  }

  const handleLoadStrategy = (strat: AlgoTestStrategy) => {
    setStrategyId(strat.id)
    setStrategyName(strat.name)
    setUnderlying(strat.underlying)
    setStrategyType(strat.strategy_type)
    setEntryTime(strat.entry_time)
    setExitTime(strat.exit_time)
    setOverallSLValue(strat.overall_sl)
    setOverallTargetValue(strat.overall_target)
    setMtmTrailWhen(strat.mtm_trail_when || 2000)
    setMtmTrailBy(strat.mtm_trail_by || 1000)
    setLegs(strat.legs || [])
    showToast.success(`Loaded strategy: ${strat.name}`)
  }

  const handleDeploy = async (mode: 'PAPER' | 'LIVE') => {
    try {
      await deploymentApi.createDeployment({
        strategy_id: strategyId,
        strategy_name: strategyName,
        underlying,
        mode,
        entry_time: entryTime,
        exit_time: exitTime,
        legs,
        overall_sl: overallSLValue,
        overall_target: overallTargetValue,
      })
      await loadDeployments()
      setActiveTab(mode === 'PAPER' ? 'forward' : 'live')
      showToast.success(`Strategy deployed in ${mode === 'PAPER' ? 'Paper Trading' : 'Live Broker'} mode!`)
    } catch (e) {
      showToast.error('Deployment failed')
    }
  }

  const handleDeploymentAction = async (id: string, action: 'SQUARE_OFF' | 'PAUSE' | 'RESUME' | 'DELETE') => {
    try {
      await deploymentApi.deploymentAction(id, action)
      await loadDeployments()
      showToast.success(`Action ${action} executed successfully!`)
    } catch (e) {
      showToast.error('Action failed')
    }
  }

  const addLeg = () => {
    setLegs([
      ...legs,
      {
        id: `leg_${Date.now()}`,
        position_type: 'BUY',
        option_type: 'CE',
        expiry: 'CURRENT_WEEK',
        lots: 1,
        strike_selection: 'OTM_1',
        sl_type: 'PERCENTAGE',
        sl_value: 30,
        target_type: 'PERCENTAGE',
        target_value: 100,
        trailing_sl: false,
        trail_when: 0,
        trail_by: 0,
        re_entry_type: 'NONE',
        momentum_type: 'NONE',
        momentum_value: 0,
      },
    ])
    showToast.success('Option Leg added')
  }

  const removeLeg = (id: string) => {
    if (legs.length <= 1) {
      showToast.error('At least 1 leg required')
      return
    }
    setLegs(legs.filter((l) => l.id !== id))
  }

  const updateLeg = (id: string, field: keyof OptionLegConfig, val: any) => {
    setLegs(legs.map((l) => (l.id === id ? { ...l, [field]: val } : l)))
  }

  const runBacktest = async () => {
    setIsBacktesting(true)
    try {
      const data = await algotestApi.runBacktest({
        underlying,
        legs,
        start_date: startDate,
        end_date: endDate,
        entry_time: entryTime,
        exit_time: exitTime,
        overall_sl: overallSLValue,
        overall_target: overallTargetValue,
      })
      setResults(data)
      setActiveTab('backtest')
      showToast.success('AlgoTest Backtest Execution Complete!')
    } catch (e) {
      showToast.error('Backtest execution failed')
    } finally {
      setIsBacktesting(false)
    }
  }

  const exportCSV = () => {
    if (!results || !results.executed_legs) return
    const headers = ['Instrument,Qty,Entry Price,Entry Time,Initial SL,Updated SL,Target,Exit Price,Exit Time,MTM (INR)\n']
    const rows = results.executed_legs.map(
      (l) => `${l.instrument},${l.qty},${l.entry_price},${l.entry_time},${l.initial_sl},${l.updated_sl},${l.target},${l.exit_price},${l.exit_time},${l.mtm}\n`
    )
    const blob = new Blob([headers.join(''), rows.join('')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${strategyName.replace(/\s+/g, '_')}_backtest_ledger.csv`
    a.click()
    showToast.success('Backtest Ledger CSV Exported!')
  }

  // Payoff calculations
  const payoffData = useMemo(() => {
    const currentSpot = spotPriceBase + simSpotShift
    const range = underlying === 'NIFTY' ? 800 : 2000
    const step = underlying === 'NIFTY' ? 20 : 50
    const points: { price: number; pnlExpiry: number; pnlT0: number }[] = []

    let maxProfit = 0
    let maxLoss = 0
    let breakevenLow = currentSpot
    let breakevenHigh = currentSpot

    let totalDelta = 0
    let totalTheta = 0
    let totalGamma = 0
    let totalVega = 0

    const lotMultiplier = underlying === 'NIFTY' ? 50 : 15

    for (let p = currentSpot - range; p <= currentSpot + range; p += step) {
      let pnlExp = 0
      let pnlNow = 0

      legs.forEach((leg) => {
        const isBuy = leg.position_type === 'BUY'
        const isCE = leg.option_type === 'CE'
        const strikeOffset = leg.strike_selection.includes('OTM_1')
          ? 100
          : leg.strike_selection.includes('OTM_2')
          ? 200
          : leg.strike_selection.includes('ITM_1')
          ? -100
          : 0
        const strike = isCE ? spotPriceBase + strikeOffset : spotPriceBase - strikeOffset
        const premium = 175.0

        let intrinsic = 0
        if (isCE) {
          intrinsic = Math.max(0, p - strike)
        } else {
          intrinsic = Math.max(0, strike - p)
        }

        const legPnlExp = (isBuy ? intrinsic - premium : premium - intrinsic) * (leg.lots * lotMultiplier)
        pnlExp += legPnlExp

        const timeDecayFactor = (4 - simDaysToExpiry) * 22
        const ivShockEffect = simIvShift * 12.5
        const currentOptionVal = Math.max(
          intrinsic,
          premium - timeDecayFactor + ivShockEffect + (p - strike) * (isCE ? 0.5 : -0.5)
        )
        const legPnlNow = (isBuy ? currentOptionVal - premium : premium - currentOptionVal) * (leg.lots * lotMultiplier)
        pnlNow += legPnlNow

        if (p === currentSpot) {
          const deltaUnit = isCE ? 0.5 : -0.5
          totalDelta += (isBuy ? deltaUnit : -deltaUnit) * (leg.lots * lotMultiplier)
          totalTheta += (isBuy ? -18.5 : 18.5) * (leg.lots * lotMultiplier)
          totalGamma += (isBuy ? 0.0025 : -0.0025) * (leg.lots * lotMultiplier)
          totalVega += (isBuy ? 14.2 : -14.2) * (leg.lots * lotMultiplier)
        }
      })

      if (pnlExp > maxProfit) maxProfit = pnlExp
      if (pnlExp < maxLoss) maxLoss = pnlExp
      points.push({ price: p, pnlExpiry: pnlExp, pnlT0: pnlNow })
    }

    for (let i = 1; i < points.length; i++) {
      if ((points[i - 1].pnlExpiry < 0 && points[i].pnlExpiry >= 0) || (points[i - 1].pnlExpiry >= 0 && points[i].pnlExpiry < 0)) {
        if (points[i].price < currentSpot) breakevenLow = points[i].price
        else breakevenHigh = points[i].price
      }
    }

    return {
      points,
      currentSpot,
      maxProfit: Math.round(maxProfit),
      maxLoss: Math.round(maxLoss),
      breakevenLow,
      breakevenHigh,
      greeks: {
        delta: Number(totalDelta.toFixed(2)),
        theta: Number(totalTheta.toFixed(2)),
        gamma: Number(totalGamma.toFixed(4)),
        vega: Number(totalVega.toFixed(2)),
      },
    }
  }, [legs, spotPriceBase, simSpotShift, simIvShift, simDaysToExpiry, underlying])

  // Marketplace Prebuilt Strategies
  const marketplaceAlgos = [
    {
      id: 'mp_1',
      title: '9:20 Short Straddle (Classic)',
      tag: 'Delta Neutral',
      author: 'AlgoTest Pro Labs',
      winRate: '69.4%',
      cagr: '38.2%',
      maxDD: '-₹14,500',
      description: 'Sells ATM CE + PE at 09:20 AM with 25% individual SL and trailing lock.',
      underlying: 'NIFTY' as const,
      legs: [
        {
          id: 'mleg_1',
          position_type: 'SELL' as const,
          option_type: 'CE' as const,
          expiry: 'CURRENT_WEEK' as const,
          lots: 1,
          strike_selection: 'ATM' as const,
          sl_type: 'PERCENTAGE' as const,
          sl_value: 25,
          target_type: 'PERCENTAGE' as const,
          target_value: 80,
          trailing_sl: true,
          trail_when: 10,
          trail_by: 5,
          re_entry_type: 'RE_ENTRY_SL' as const,
          momentum_type: 'NONE' as const,
          momentum_value: 0,
        },
        {
          id: 'mleg_2',
          position_type: 'SELL' as const,
          option_type: 'PE' as const,
          expiry: 'CURRENT_WEEK' as const,
          lots: 1,
          strike_selection: 'ATM' as const,
          sl_type: 'PERCENTAGE' as const,
          sl_value: 25,
          target_type: 'PERCENTAGE' as const,
          target_value: 80,
          trailing_sl: true,
          trail_when: 10,
          trail_by: 5,
          re_entry_type: 'RE_ENTRY_SL' as const,
          momentum_type: 'NONE' as const,
          momentum_value: 0,
        },
      ],
    },
    {
      id: 'mp_2',
      title: 'BankNifty Weekly Iron Condor',
      tag: 'Defined Risk',
      author: 'Quant Alpha India',
      winRate: '76.2%',
      cagr: '29.5%',
      maxDD: '-₹8,900',
      description: 'Sells OTM 1 CE/PE and hedges with OTM 3 wings for strict risk control.',
      underlying: 'BANKNIFTY' as const,
      legs: [
        {
          id: 'mleg_3',
          position_type: 'SELL' as const,
          option_type: 'CE' as const,
          expiry: 'CURRENT_WEEK' as const,
          lots: 1,
          strike_selection: 'OTM_1' as const,
          sl_type: 'PERCENTAGE' as const,
          sl_value: 35,
          target_type: 'PERCENTAGE' as const,
          target_value: 75,
          trailing_sl: false,
          trail_when: 0,
          trail_by: 0,
          re_entry_type: 'NONE' as const,
          momentum_type: 'NONE' as const,
          momentum_value: 0,
        },
        {
          id: 'mleg_4',
          position_type: 'SELL' as const,
          option_type: 'PE' as const,
          expiry: 'CURRENT_WEEK' as const,
          lots: 1,
          strike_selection: 'OTM_1' as const,
          sl_type: 'PERCENTAGE' as const,
          sl_value: 35,
          target_type: 'PERCENTAGE' as const,
          target_value: 75,
          trailing_sl: false,
          trail_when: 0,
          trail_by: 0,
          re_entry_type: 'NONE' as const,
          momentum_type: 'NONE' as const,
          momentum_value: 0,
        },
        {
          id: 'mleg_5',
          position_type: 'BUY' as const,
          option_type: 'CE' as const,
          expiry: 'CURRENT_WEEK' as const,
          lots: 1,
          strike_selection: 'OTM_3' as const,
          sl_type: 'PERCENTAGE' as const,
          sl_value: 50,
          target_type: 'PERCENTAGE' as const,
          target_value: 100,
          trailing_sl: false,
          trail_when: 0,
          trail_by: 0,
          re_entry_type: 'NONE' as const,
          momentum_type: 'NONE' as const,
          momentum_value: 0,
        },
        {
          id: 'mleg_6',
          position_type: 'BUY' as const,
          option_type: 'PE' as const,
          expiry: 'CURRENT_WEEK' as const,
          lots: 1,
          strike_selection: 'OTM_3' as const,
          sl_type: 'PERCENTAGE' as const,
          sl_value: 50,
          target_type: 'PERCENTAGE' as const,
          target_value: 100,
          trailing_sl: false,
          trail_when: 0,
          trail_by: 0,
          re_entry_type: 'NONE' as const,
          momentum_type: 'NONE' as const,
          momentum_value: 0,
        },
      ],
    },
    {
      id: 'mp_3',
      title: '0DTE Expiry Day Scalper Pro',
      tag: 'High Gamma',
      author: 'Options Sniper Lab',
      winRate: '65.8%',
      cagr: '52.1%',
      maxDD: '-₹18,200',
      description: 'Aggressive theta decay capture on weekly expiry day with fast re-entries.',
      underlying: 'NIFTY' as const,
      legs: [
        {
          id: 'mleg_7',
          position_type: 'SELL' as const,
          option_type: 'CE' as const,
          expiry: 'CURRENT_WEEK' as const,
          lots: 2,
          strike_selection: 'ATM' as const,
          sl_type: 'PERCENTAGE' as const,
          sl_value: 20,
          target_type: 'PERCENTAGE' as const,
          target_value: 85,
          trailing_sl: true,
          trail_when: 15,
          trail_by: 5,
          re_entry_type: 'RE_ENTRY_SL' as const,
          momentum_type: 'NONE' as const,
          momentum_value: 0,
        },
        {
          id: 'mleg_8',
          position_type: 'SELL' as const,
          option_type: 'PE' as const,
          expiry: 'CURRENT_WEEK' as const,
          lots: 2,
          strike_selection: 'ATM' as const,
          sl_type: 'PERCENTAGE' as const,
          sl_value: 20,
          target_type: 'PERCENTAGE' as const,
          target_value: 85,
          trailing_sl: true,
          trail_when: 15,
          trail_by: 5,
          re_entry_type: 'RE_ENTRY_SL' as const,
          momentum_type: 'NONE' as const,
          momentum_value: 0,
        },
      ],
    },
  ]

  const importMarketplaceAlgo = (algo: (typeof marketplaceAlgos)[0]) => {
    setStrategyName(algo.title)
    setUnderlying(algo.underlying)
    setLegs(algo.legs)
    setActiveTab('builder')
    showToast.success(`Loaded "${algo.title}" into Strategy Builder!`)
  }

  return (
    <div className="flex min-h-screen flex-col bg-[#0b0e14] text-slate-100 antialiased font-sans">
      {/* Top Header */}
      <header className="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-slate-800 bg-[#0d111a] px-4 md:px-8">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 cursor-pointer" onClick={() => setActiveTab('builder')}>
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 font-bold text-white shadow-lg shadow-cyan-500/20">
              AT
            </div>
            <span className="text-lg font-bold tracking-tight text-white">
              Algo<span className="text-cyan-400">Test</span>
              <Badge variant="outline" className="ml-2 text-[10px] text-cyan-400 border-cyan-500/30 bg-cyan-500/10">
                PRO
              </Badge>
            </span>
          </div>

          {/* Navigation Tabs */}
          <nav className="hidden md:flex items-center space-x-1">
            {[
              { id: 'builder', label: 'Strategy Builder', icon: Layers },
              { id: 'backtest', label: 'Backtesting', icon: BarChart2 },
              { id: 'simulator', label: 'Simulator & Payoff', icon: Sliders },
              { id: 'signals', label: 'Signals AI', icon: Cpu },
              { id: 'marketplace', label: 'Marketplace', icon: Sparkles },
              { id: 'forward', label: 'Forward Testing', icon: Activity },
              { id: 'live', label: 'Live Deployment', icon: Zap },
              { id: 'analytics', label: 'Heatmap & Analytics', icon: Calendar },
            ].map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                    isActive
                      ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 font-semibold'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className={`h-3.5 w-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  {tab.label}
                </button>
              )
            })}
          </nav>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            size="sm"
            variant="outline"
            onClick={handleSaveStrategy}
            disabled={isSaving}
            className="h-8 border-slate-700 hover:bg-slate-800 text-slate-300 text-xs gap-1.5"
          >
            <Save className="h-3.5 w-3.5 text-cyan-400" />
            {isSaving ? 'Saving...' : 'Save Strategy'}
          </Button>

          <Button
            size="sm"
            onClick={runBacktest}
            disabled={isBacktesting}
            className="h-8 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white font-semibold text-xs shadow-md shadow-cyan-500/20"
          >
            {isBacktesting ? (
              <>
                <RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" /> Running...
              </>
            ) : (
              <>
                <Play className="mr-1.5 h-3.5 w-3.5 fill-current" /> Start Backtest
              </>
            )}
          </Button>
        </div>
      </header>

      {/* Body Content */}
      <main className="flex-1 p-4 md:p-6 max-w-7xl mx-auto w-full">
        {/* ========================================================= */}
        {/* TAB 1: STRATEGY BUILDER */}
        {/* ========================================================= */}
        {activeTab === 'builder' && (
          <div className="space-y-6">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 bg-[#111622] border border-slate-800 p-4 rounded-xl">
              <div className="flex-1 w-full">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Strategy Name</span>
                <input
                  type="text"
                  value={strategyName}
                  onChange={(e) => setStrategyName(e.target.value)}
                  className="bg-transparent text-sm font-bold text-white border-b border-slate-700 hover:border-cyan-500 focus:border-cyan-500 outline-none w-full py-1 mt-0.5"
                />
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  className="h-8 bg-blue-600/90 hover:bg-blue-600 text-white text-xs gap-1"
                  onClick={() => handleDeploy('PAPER')}
                >
                  <Activity className="h-3.5 w-3.5" /> Deploy Paper Trade
                </Button>
                <Button
                  size="sm"
                  className="h-8 bg-emerald-600/90 hover:bg-emerald-600 text-white text-xs gap-1"
                  onClick={() => handleDeploy('LIVE')}
                >
                  <Zap className="h-3.5 w-3.5" /> Deploy Live Broker
                </Button>
              </div>
            </div>

            {/* Top Parameters */}
            <Card className="bg-[#111622] border-slate-800 p-5 rounded-xl">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label className="text-xs font-semibold text-slate-400">Underlying Index</label>
                  <div className="flex gap-1 mt-1.5">
                    {['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX'].map((idx) => (
                      <button
                        key={idx}
                        onClick={() => setUnderlying(idx as any)}
                        className={`px-3 py-1 text-xs rounded font-medium transition-all ${
                          underlying === idx
                            ? 'bg-cyan-500 text-white font-bold shadow-md shadow-cyan-500/30'
                            : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                        }`}
                      >
                        {idx}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-400">Strategy Type</label>
                  <div className="flex gap-1 mt-1.5">
                    {['INTRADAY', 'BTST', 'POSITIONAL'].map((t) => (
                      <button
                        key={t}
                        onClick={() => setStrategyType(t as any)}
                        className={`px-3 py-1 text-xs rounded font-medium transition-all ${
                          strategyType === t ? 'bg-blue-600 text-white font-bold' : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-400">Entry & Exit Times</label>
                  <div className="flex items-center gap-2 mt-1.5">
                    <input
                      type="time"
                      value={entryTime}
                      onChange={(e) => setEntryTime(e.target.value)}
                      className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white outline-none w-18"
                    />
                    <span className="text-xs text-slate-500">to</span>
                    <input
                      type="time"
                      value={exitTime}
                      onChange={(e) => setExitTime(e.target.value)}
                      className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white outline-none w-18"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-400">Backtest Period</label>
                  <div className="flex items-center gap-2 mt-1.5">
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white outline-none w-28"
                    />
                    <span className="text-xs text-slate-500">to</span>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white outline-none w-28"
                    />
                  </div>
                </div>
              </div>
            </Card>

            {/* Options Legs Section */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300">
                    Options Legs ({legs.length})
                  </h2>
                  <Badge variant="outline" className="text-xs text-slate-400 border-slate-700">
                    Individual Leg SL, Target, Trailing & Re-entry
                  </Badge>
                </div>

                <Button onClick={addLeg} size="sm" variant="outline" className="h-8 border-cyan-500/40 text-cyan-400 text-xs">
                  <Plus className="mr-1 h-3.5 w-3.5" /> Add New Leg
                </Button>
              </div>

              {legs.map((leg, idx) => (
                <Card key={leg.id} className="bg-[#111622] border-slate-800 p-4 rounded-xl">
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
                    <div className="md:col-span-2 flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-500">#{idx + 1}</span>
                      <div className="flex rounded overflow-hidden border border-slate-700">
                        <button
                          onClick={() => updateLeg(leg.id, 'position_type', 'BUY')}
                          className={`px-2.5 py-1 text-xs font-bold ${
                            leg.position_type === 'BUY' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          BUY
                        </button>
                        <button
                          onClick={() => updateLeg(leg.id, 'position_type', 'SELL')}
                          className={`px-2.5 py-1 text-xs font-bold ${
                            leg.position_type === 'SELL' ? 'bg-rose-600 text-white' : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          SELL
                        </button>
                      </div>
                    </div>

                    <div className="md:col-span-3 flex items-center gap-2">
                      <div className="flex rounded overflow-hidden border border-slate-700">
                        <button
                          onClick={() => updateLeg(leg.id, 'option_type', 'CE')}
                          className={`px-2 py-1 text-xs font-bold ${
                            leg.option_type === 'CE' ? 'bg-cyan-600 text-white' : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          CE
                        </button>
                        <button
                          onClick={() => updateLeg(leg.id, 'option_type', 'PE')}
                          className={`px-2 py-1 text-xs font-bold ${
                            leg.option_type === 'PE' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          PE
                        </button>
                      </div>

                      <select
                        value={leg.strike_selection}
                        onChange={(e) => updateLeg(leg.id, 'strike_selection', e.target.value)}
                        className="bg-slate-800 border border-slate-700 text-xs text-white rounded px-2 py-1 outline-none"
                      >
                        <option value="ATM">ATM (Strike 0)</option>
                        <option value="OTM_1">OTM 1 Strike</option>
                        <option value="OTM_2">OTM 2 Strike</option>
                        <option value="OTM_3">OTM 3 Strike</option>
                        <option value="ITM_1">ITM 1 Strike</option>
                      </select>
                    </div>

                    <div className="md:col-span-1">
                      <div className="flex items-center bg-slate-800 border border-slate-700 rounded px-2 py-1">
                        <span className="text-[10px] text-slate-400 mr-1">Lots:</span>
                        <input
                          type="number"
                          value={leg.lots}
                          min={1}
                          onChange={(e) => updateLeg(leg.id, 'lots', Number(e.target.value))}
                          className="bg-transparent text-xs text-white w-8 outline-none font-bold"
                        />
                      </div>
                    </div>

                    <div className="md:col-span-3 flex items-center gap-2">
                      <div className="flex items-center bg-slate-800/90 border border-rose-500/30 rounded px-2 py-1">
                        <span className="text-[10px] text-rose-400 font-bold mr-1">SL:</span>
                        <input
                          type="number"
                          value={leg.sl_value}
                          onChange={(e) => updateLeg(leg.id, 'sl_value', Number(e.target.value))}
                          className="bg-transparent text-xs text-rose-200 w-10 outline-none font-bold"
                        />
                        <span className="text-[10px] text-rose-400">%</span>
                      </div>

                      <div className="flex items-center bg-slate-800/90 border border-emerald-500/30 rounded px-2 py-1">
                        <span className="text-[10px] text-emerald-400 font-bold mr-1">TP:</span>
                        <input
                          type="number"
                          value={leg.target_value}
                          onChange={(e) => updateLeg(leg.id, 'target_value', Number(e.target.value))}
                          className="bg-transparent text-xs text-emerald-200 w-10 outline-none font-bold"
                        />
                        <span className="text-[10px] text-emerald-400">%</span>
                      </div>
                    </div>

                    <div className="md:col-span-2">
                      <select
                        value={leg.re_entry_type}
                        onChange={(e) => updateLeg(leg.id, 're_entry_type', e.target.value)}
                        className="bg-slate-800 border border-slate-700 text-[11px] text-slate-300 rounded px-2 py-1 outline-none w-full"
                      >
                        <option value="NONE">No Re-entry</option>
                        <option value="RE_ENTRY_SL">Re-entry on SL</option>
                        <option value="RE_EXECUTE_SL">Re-execute on SL</option>
                      </select>
                    </div>

                    <div className="md:col-span-1 flex justify-end">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => removeLeg(leg.id)}
                        className="h-7 w-7 text-slate-500 hover:text-rose-400"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>

            {/* Overall MTM Risk Controls */}
            <Card className="bg-[#111622] border-slate-800 p-5 rounded-xl">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-1.5">
                <Shield className="h-4 w-4 text-cyan-400" /> Overall Strategy Risk & MTM Controls
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-800">
                  <span className="text-xs text-slate-400">Total Strategy Stop Loss (MTM)</span>
                  <div className="flex items-center mt-2 gap-2">
                    <span className="text-xs font-bold text-rose-400">₹</span>
                    <input
                      type="number"
                      value={overallSLValue}
                      onChange={(e) => setOverallSLValue(Number(e.target.value))}
                      className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white font-bold w-24 outline-none"
                    />
                  </div>
                </div>

                <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-800">
                  <span className="text-xs text-slate-400">Total Strategy Target (MTM)</span>
                  <div className="flex items-center mt-2 gap-2">
                    <span className="text-xs font-bold text-emerald-400">₹</span>
                    <input
                      type="number"
                      value={overallTargetValue}
                      onChange={(e) => setOverallTargetValue(Number(e.target.value))}
                      className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white font-bold w-24 outline-none"
                    />
                  </div>
                </div>

                <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-800">
                  <span className="text-xs text-slate-400">Trailing Overall Stop Loss</span>
                  <div className="flex items-center mt-2 gap-2">
                    <span className="text-[11px] text-slate-400">When MTM reaches ₹{mtmTrailWhen}, Lock ₹{mtmTrailBy}</span>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 4: SIGNALS AI (AUTOMATED INDICATOR TRIGGERS) */}
        {/* ========================================================= */}
        {activeTab === 'signals' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200">
                  Signals AI - Real-Time Strategy Trigger Engine
                </h2>
                <p className="text-xs text-slate-400">
                  Execute options legs automatically when technical indicator conditions are met on spot or combined premium
                </p>
              </div>
              <Badge className="bg-cyan-500/20 text-cyan-400 border-cyan-500/30 text-xs flex items-center gap-1">
                <Cpu className="h-3.5 w-3.5" /> AI Engine Ready
              </Badge>
            </div>

            <Card className="bg-[#111622] border-slate-800 p-5 rounded-xl space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-xs font-semibold text-slate-400">Select Signal Indicator</label>
                  <select
                    value={signalIndicator}
                    onChange={(e) => setSignalIndicator(e.target.value as any)}
                    className="mt-1.5 bg-slate-800 border border-slate-700 text-xs text-white rounded p-2 outline-none w-full font-medium"
                  >
                    <option value="SUPERTREND">SuperTrend (ATR)</option>
                    <option value="VWAP">Anchored VWAP Breakout</option>
                    <option value="EMA_CROSS">EMA 9 / 21 Crossover</option>
                    <option value="PREMIUM_MOMENTUM">Combined Premium Decay Momentum</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-400">Signal Timeframe</label>
                  <div className="flex gap-1 mt-1.5">
                    {['1m', '3m', '5m', '15m'].map((tf) => (
                      <button
                        key={tf}
                        onClick={() => setSignalTimeframe(tf as any)}
                        className={`px-3 py-1.5 text-xs rounded font-medium transition-all ${
                          signalTimeframe === tf ? 'bg-cyan-500 text-white font-bold' : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {tf}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-400">Execution Action on Signal</label>
                  <select
                    value={signalAction}
                    onChange={(e) => setSignalAction(e.target.value as any)}
                    className="mt-1.5 bg-slate-800 border border-slate-700 text-xs text-white rounded p-2 outline-none w-full font-medium"
                  >
                    <option value="BUY_CALL_SELL_PUT">Bullish Signal: Buy ATM CE / Sell PE</option>
                    <option value="BUY_PUT_SELL_CALL">Bearish Signal: Buy ATM PE / Sell CE</option>
                    <option value="ATM_STRADDLE">Rangebound Signal: Sell ATM Straddle</option>
                  </select>
                </div>
              </div>

              {/* Indicator Parameter Config */}
              <div className="p-4 rounded-lg bg-slate-900/80 border border-slate-800 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <span className="text-xs font-semibold text-slate-400">Indicator Primary Period / Length</span>
                  <div className="flex items-center mt-1.5 gap-2">
                    <input
                      type="number"
                      value={signalParam1}
                      onChange={(e) => setSignalParam1(Number(e.target.value))}
                      className="bg-slate-800 border border-slate-700 rounded px-2.5 py-1 text-xs text-white font-bold w-20 outline-none"
                    />
                    <span className="text-xs text-slate-500">(e.g. SuperTrend Period: 10 or Fast EMA: 9)</span>
                  </div>
                </div>

                <div>
                  <span className="text-xs font-semibold text-slate-400">Multiplier / Secondary Period</span>
                  <div className="flex items-center mt-1.5 gap-2">
                    <input
                      type="number"
                      value={signalParam2}
                      onChange={(e) => setSignalParam2(Number(e.target.value))}
                      className="bg-slate-800 border border-slate-700 rounded px-2.5 py-1 text-xs text-white font-bold w-20 outline-none"
                    />
                    <span className="text-xs text-slate-500">(e.g. SuperTrend Multiplier: 3 or Slow EMA: 21)</span>
                  </div>
                </div>
              </div>

              <div className="flex justify-end">
                <Button
                  className="bg-cyan-600 hover:bg-cyan-700 text-white text-xs font-semibold"
                  onClick={() => showToast.success('Signals AI Rule Created & Linked to Strategy!')}
                >
                  <Cpu className="mr-1.5 h-3.5 w-3.5" /> Activate Signals AI Automation
                </Button>
              </div>
            </Card>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 5: MARKETPLACE (PRE-BUILT POPULAR STRATEGIES) */}
        {/* ========================================================= */}
        {activeTab === 'marketplace' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200">
                  Strategy Marketplace & Portfolios
                </h2>
                <p className="text-xs text-slate-400">
                  Tested and verified options algorithms created by research analysts and quantitative traders
                </p>
              </div>
              <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-xs flex items-center gap-1">
                <Sparkles className="h-3.5 w-3.5" /> Curated RA Algos
              </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {marketplaceAlgos.map((algo) => (
                <Card
                  key={algo.id}
                  className="bg-[#111622] border-slate-800 p-5 rounded-xl hover:border-slate-700 transition-all flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Badge className="bg-slate-800 border-slate-700 text-cyan-400 text-[10px]">{algo.tag}</Badge>
                      <span className="text-[11px] font-bold text-slate-400">{algo.underlying}</span>
                    </div>

                    <div>
                      <h3 className="text-sm font-bold text-white">{algo.title}</h3>
                      <span className="text-[11px] text-slate-500">By {algo.author}</span>
                    </div>

                    <p className="text-xs text-slate-400 line-clamp-2">{algo.description}</p>

                    <div className="grid grid-cols-3 gap-2 bg-slate-900/80 p-2.5 rounded-lg border border-slate-800/80 text-center">
                      <div>
                        <span className="text-[10px] text-slate-500">Win Rate</span>
                        <p className="text-xs font-bold text-emerald-400">{algo.winRate}</p>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500">CAGR</span>
                        <p className="text-xs font-bold text-cyan-400">{algo.cagr}</p>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500">Max DD</span>
                        <p className="text-xs font-bold text-rose-400">{algo.maxDD}</p>
                      </div>
                    </div>
                  </div>

                  <Button
                    size="sm"
                    className="w-full mt-4 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold gap-1.5"
                    onClick={() => importMarketplaceAlgo(algo)}
                  >
                    <Download className="h-3.5 w-3.5 text-cyan-400" /> 1-Click Import Strategy
                  </Button>
                </Card>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
