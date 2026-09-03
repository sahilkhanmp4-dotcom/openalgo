import { apiClient } from './client'

export interface OptionLegConfig {
  id: string
  position_type: 'BUY' | 'SELL'
  option_type: 'CE' | 'PE'
  expiry: 'CURRENT_WEEK' | 'NEXT_WEEK' | 'MONTHLY'
  lots: number
  strike_selection: 'ATM' | 'OTM_1' | 'OTM_2' | 'OTM_3' | 'ITM_1' | 'ITM_2' | 'DELTA'
  sl_type: 'PERCENTAGE' | 'POINTS' | 'UNDERLYING_PERCENT'
  sl_value: number
  target_type: 'PERCENTAGE' | 'POINTS' | 'UNDERLYING_PERCENT'
  target_value: number
  trailing_sl: boolean
  trail_when: number
  trail_by: number
  re_entry_type: 'NONE' | 'RE_ENTRY_SL' | 'RE_EXECUTE_SL' | 'RE_ENTRY_TP'
  momentum_type: 'NONE' | 'POINTS_UP' | 'PERCENT_UP'
  momentum_value: number
}

export interface AlgoTestStrategy {
  id: string
  name: string
  underlying: 'NIFTY' | 'BANKNIFTY' | 'FINNIFTY' | 'SENSEX'
  strategy_type: 'INTRADAY' | 'BTST' | 'POSITIONAL'
  entry_time: string
  exit_time: string
  overall_sl: number
  overall_target: number
  mtm_trail_when: number
  mtm_trail_by: number
  legs: OptionLegConfig[]
  created_at?: string
  updated_at?: string
}

export interface BacktestResponseData {
  total_pnl: number
  win_rate: number
  total_days: number
  winning_days: number
  losing_days: number
  max_drawdown: number
  max_drawdown_days: number
  avg_daily_pnl: number
  profit_factor: number
  sharpe_ratio: number
  calmar_ratio: number
  max_winning_streak: number
  max_losing_streak: number
  executed_legs: {
    instrument: string
    qty: number
    entry_price: number
    entry_time: string
    initial_sl: number
    updated_sl: number
    target: number
    exit_price: number
    exit_time: string
    mtm: number
  }[]
  daily_pnl: {
    date: string
    pnl: number
    win: boolean
  }[]
}

export const algotestApi = {
  getStrategies: async (): Promise<AlgoTestStrategy[]> => {
    const res = await apiClient.get<{ status: string; data: AlgoTestStrategy[] }>('/api/v1/algotest/strategies')
    return res.data.data
  },

  saveStrategy: async (strategy: Partial<AlgoTestStrategy>): Promise<AlgoTestStrategy> => {
    const res = await apiClient.post<{ status: string; data: AlgoTestStrategy }>('/api/v1/algotest/strategies', strategy)
    return res.data.data
  },

  deleteStrategy: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v1/algotest/strategies/${id}`)
  },

  runBacktest: async (payload: {
    underlying: string
    legs: OptionLegConfig[]
    start_date: string
    end_date: string
    entry_time: string
    exit_time: string
    overall_sl: number
    overall_target: number
  }): Promise<BacktestResponseData> => {
    const res = await apiClient.post<{ status: string; data: BacktestResponseData }>('/api/v1/algotest/backtest', payload)
    return res.data.data
  },
}

export interface AlgoDeployment {
  id: string
  strategy_id: string
  strategy_name: string
  underlying: string
  mode: 'PAPER' | 'LIVE'
  status: 'ACTIVE' | 'PAUSED' | 'SQUARED_OFF'
  entry_time: string
  exit_time: string
  legs: OptionLegConfig[]
  overall_sl: number
  overall_target: number
  current_mtm: number
  deployed_at: string
}

export const deploymentApi = {
  getDeployments: async (): Promise<AlgoDeployment[]> => {
    const res = await apiClient.get<{ status: string; data: AlgoDeployment[] }>('/api/v1/algotest/deployments')
    return res.data.data
  },

  createDeployment: async (payload: Partial<AlgoDeployment>): Promise<AlgoDeployment> => {
    const res = await apiClient.post<{ status: string; data: AlgoDeployment }>('/api/v1/algotest/deployments', payload)
    return res.data.data
  },

  deploymentAction: async (id: string, action: 'SQUARE_OFF' | 'PAUSE' | 'RESUME' | 'DELETE'): Promise<void> => {
    await apiClient.post(`/api/v1/algotest/deployments/${id}/action`, { action })
  }
}
