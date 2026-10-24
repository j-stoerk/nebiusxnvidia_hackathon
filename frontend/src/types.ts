export type Session = {
  vehicle_id: string;
  arrival_time: string;
  departure_time: string;
  energy_required_kwh: number;
  max_charging_power_kw: number;
  connector_type: string;
};
export type Charger = {
  charger_id: string;
  max_power_kw: number;
  connector_type: string;
  available: boolean;
};
export type Station = {
  station_id: string;
  simulated: boolean;
  timezone: "UTC";
  slot_minutes: 15;
  station_power_limit_kw: number;
  charging_efficiency: number;
  chargers: Charger[];
};
export type Allocation = {
  vehicle_id: string;
  charger_id: string;
  start_time: string;
  end_time: string;
  power_kw: number;
  charging_efficiency: number;
};
export type VehicleMetric = {
  vehicle_id: string;
  required_kwh: number;
  delivered_kwh: number;
  shortfall_kwh: number;
  target_met: boolean;
  departure_time: string;
  arrival_time: string;
};
export type Metrics = {
  cost_eur: number;
  peak_power_kw: number;
  delivered_kwh: number;
  unserved_kwh: number;
  target_success_percent: number;
  vehicles: VehicleMetric[];
  power_series: {
    timestamp: string;
    power_kw: number;
    price_eur_per_kwh: number;
  }[];
};
export type Schedule = {
  kind: string;
  allocations: Allocation[];
  metrics: Metrics;
  validated: boolean;
  solver_status: string;
  state_version: number;
  schedule_version: number;
  runtime_seconds: number;
  shortfall_optimal: boolean;
  cost_optimal: boolean;
};
export type SimEvent = {
  event_id: string;
  type: "CHARGER_FAILED" | "CHARGER_RECOVERED" | "PRICE_CHANGED";
  charger_id?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  time?: string | null;
  add_eur_per_kwh?: number | null;
};
export type Workspace = {
  workspace_id: string;
  label: string;
  simulated: boolean;
  state_version: number;
  schedule_version: number;
  now: string;
  horizon_start: string;
  horizon_end: string;
  station: Station;
  sessions: Session[];
  analytics: {
    vehicles: number;
    total_energy_required_kwh: number;
    horizon_hours: number;
    available_chargers: number;
    warnings: {
      vehicle_id: string;
      minimum_shortfall_kwh: number;
      reason: string;
    }[];
  };
  baseline: Schedule | null;
  optimized: Schedule | null;
  stale: boolean;
  last_error: string | null;
  recovery_seconds: number | null;
  history_records: number;
  events: SimEvent[];
  comparison: {
    equal_delivered_energy: boolean;
    cost_savings_eur: number | null;
    cost_savings_percent: number | null;
  } | null;
  agent: { configured: boolean; model: string | null; reason: string | null };
  charger_status: { charger_id: string; available_now: boolean }[];
};
export type Reply = {
  mode: string;
  message: string;
  model: string | null;
  tool_calls: { name: string; result: unknown }[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  reply?: Reply;
};
