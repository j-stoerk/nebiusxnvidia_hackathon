import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowRight,
  Check,
  PlugZap,
  RefreshCw,
  Search,
  Settings2,
  TriangleAlert,
} from "lucide-react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Schedule, SimEvent, Workspace } from "../types";
import { date, money, number, time } from "../format";

export function Metric({
  title,
  value,
  unit,
  icon,
  detail,
  positive,
  warning,
}: {
  title: string;
  value: string;
  unit?: string;
  icon: ReactNode;
  detail: string;
  positive?: boolean;
  warning?: boolean;
}) {
  return (
    <article className="metric">
      <div className="metric-label">
        {title}
        <span className="metric-icon">{icon}</span>
      </div>
      <div className="metric-value">
        {value}
        <small>{unit}</small>
      </div>
      <div
        className={`metric-detail ${positive ? "positive" : ""} ${warning ? "warn-text" : ""}`}
      >
        {positive && <span className="mini-arrow">↘</span>}
        {detail}
      </div>
    </article>
  );
}

export function PanelTitle({
  eyebrow,
  title,
  right,
}: {
  eyebrow: string;
  title: string;
  right?: ReactNode;
}) {
  return (
    <div className="panel-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h2>{title}</h2>
      </div>
      {right}
    </div>
  );
}

export function PowerChart({ workspace }: { workspace: Workspace }) {
  const rows = useMemo(
    () =>
      (workspace.baseline?.metrics.power_series || []).map((row, i) => ({
        timestamp: row.timestamp,
        baseline: row.power_kw,
        optimized: workspace.optimized?.metrics.power_series[i]?.power_kw,
        price: row.price_eur_per_kwh,
      })),
    [workspace],
  );
  return (
    <div
      className="power-chart"
      role="img"
      aria-label="Station power and electricity price over time"
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={rows}
          margin={{ top: 16, right: 12, left: -20, bottom: 2 }}
        >
          <defs>
            <linearGradient id="powerFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#337b55" stopOpacity={0.19} />
              <stop offset="100%" stopColor="#337b55" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#edf0e9" vertical={false} />
          <XAxis
            dataKey="timestamp"
            tickFormatter={time}
            minTickGap={35}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "#879187" }}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "#879187" }}
            tickFormatter={(value) => number(Number(value), 0)}
            domain={[
              0,
              (max: number) =>
                Math.max(max, workspace.station.station_power_limit_kw) * 1.1,
            ]}
          />
          <YAxis
            yAxisId="price"
            orientation="right"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 10, fill: "#a4885e" }}
            width={38}
            tickFormatter={(value) => `${Number(value).toFixed(2)}`}
          />
          <Tooltip
            labelFormatter={(value) =>
              `${date(String(value))} ${time(String(value))} UTC`
            }
            formatter={(value, name) => [
              name === "price"
                ? `${money(Number(value))}/kWh`
                : `${number(Number(value))} kW`,
              name === "optimized"
                ? "Optimized"
                : name === "baseline"
                  ? "FCFS"
                  : "Price",
            ]}
            contentStyle={{
              borderRadius: 10,
              border: "1px solid #e0e7dc",
              fontSize: 12,
            }}
          />
          <ReferenceLine
            y={workspace.station.station_power_limit_kw}
            stroke="#8a9b88"
            strokeDasharray="4 4"
            label={{
              value: "Station limit",
              position: "insideTopLeft",
              fontSize: 10,
              fill: "#879187",
            }}
          />
          <Area
            type="stepAfter"
            dataKey="optimized"
            stroke="#2c754d"
            fill="url(#powerFill)"
            strokeWidth={2.5}
            isAnimationActive={false}
          />
          <Line
            type="stepAfter"
            dataKey="baseline"
            stroke="#b5bdb2"
            strokeDasharray="4 3"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            yAxisId="price"
            type="stepAfter"
            dataKey="price"
            stroke="#c8994d"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function StationPanel({
  workspace,
  onSettings,
  disabled,
}: {
  workspace: Workspace;
  onSettings: () => void;
  disabled: boolean;
}) {
  const available = workspace.charger_status.filter(
    (c) => c.available_now,
  ).length;
  return (
    <section className="panel station-panel">
      <PanelTitle
        eyebrow="STATION HEALTH"
        title="Capacity, at a glance."
        right={
          <button
            className="icon-button"
            aria-label="Station settings"
            disabled={disabled}
            onClick={onSettings}
          >
            <Settings2 size={18} />
          </button>
        }
      />
      <div className="station-count">
        <strong>
          {available}
          <span> / {workspace.station.chargers.length}</span>
        </strong>
        <span>
          chargers available
          <br />
          at {time(workspace.now)} UTC
        </span>
      </div>
      <div className="charger-grid">
        {workspace.station.chargers.map((charger) => {
          const status = workspace.charger_status.find(
            (c) => c.charger_id === charger.charger_id,
          );
          return (
            <div
              key={charger.charger_id}
              className={`charger ${status?.available_now ? "" : "unavailable"}`}
              title={`${charger.charger_id}: ${number(charger.max_power_kw)} kW, ${charger.connector_type}, ${status?.available_now ? "available" : "unavailable"}`}
            >
              <PlugZap size={18} />
              <small>{charger.charger_id.replace("CH-", "")}</small>
            </div>
          );
        })}
      </div>
      <div className="station-row">
        <span>Station power limit</span>
        <strong>{number(workspace.station.station_power_limit_kw)} kW</strong>
      </div>
      <div className="station-row">
        <span>Charging efficiency</span>
        <strong>{number(workspace.station.charging_efficiency * 100)}%</strong>
      </div>
      <div className="station-row">
        <span>Simulation events</span>
        <strong>{workspace.events.length}</strong>
      </div>
      <div className="station-note">
        <span className="status-dot" />
        {workspace.events.length
          ? "Availability includes applied events"
          : "Simulated station · ready to plan"}
      </div>
    </section>
  );
}

export function Timeline({
  workspace,
  schedule,
  limit,
}: {
  workspace: Workspace;
  schedule: Schedule | null;
  limit?: number;
}) {
  const [filter, setFilter] = useState("");
  const start = Date.parse(workspace.horizon_start),
    span = Date.parse(workspace.horizon_end) - start;
  const position = (value: string) =>
    (100 * (Date.parse(value) - start)) / span;
  const sessions = workspace.sessions
    .filter((s) => s.vehicle_id.toLowerCase().includes(filter.toLowerCase()))
    .slice(0, limit);
  const ticks = Array.from({ length: 5 }, (_, i) =>
    new Date(start + (span * i) / 4).toISOString(),
  );
  return (
    <div className="timeline-container">
      {!limit && (
        <label className="search-box">
          <Search size={16} />
          <input
            aria-label="Filter timeline by vehicle"
            placeholder="Find a vehicle…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </label>
      )}
      <div className="timeline-axis">
        <span>VEHICLE</span>
        <div>
          {ticks.map((tick, i) => (
            <span
              key={tick}
              style={{
                left: `${25 * i}%`,
                transform: i === 4 ? "translateX(-100%)" : undefined,
              }}
            >
              {time(tick)}
            </span>
          ))}
        </div>
      </div>
      <div className={`timeline-rows ${limit ? "" : "full-timeline"}`}>
        {sessions.map((session) => (
          <div className="timeline-row" key={session.vehicle_id}>
            <span>{session.vehicle_id}</span>
            <div className="timeline-track">
              <div
                className="availability-bar"
                style={{
                  left: `${position(session.arrival_time)}%`,
                  width: `${position(session.departure_time) - position(session.arrival_time)}%`,
                }}
                title={`Available ${time(session.arrival_time)}–${time(session.departure_time)}`}
              />
              {schedule?.allocations
                .filter((a) => a.vehicle_id === session.vehicle_id)
                .map((record, i) => (
                  <div
                    key={i}
                    className={`charging-bar ${schedule.kind === "baseline" ? "baseline-bar" : ""}`}
                    style={{
                      left: `${position(record.start_time)}%`,
                      width: `${Math.max(0.1, position(record.end_time) - position(record.start_time))}%`,
                    }}
                    title={`${session.vehicle_id} · ${record.charger_id} · ${time(record.start_time)}–${time(record.end_time)} UTC · ${number(record.power_kw, 2)} kW`}
                  />
                ))}
              {workspace.now !== workspace.horizon_start && (
                <div
                  className="now-line"
                  style={{ left: `${position(workspace.now)}%` }}
                />
              )}
            </div>
          </div>
        ))}
      </div>
      {sessions.length === 0 && (
        <p className="empty-inline">No matching vehicles.</p>
      )}
      <div className="timeline-footer">
        <span>
          <span className="legend-block" />
          Scheduled charging
        </span>
        <span>
          <span className="legend-block pale" />
          Available window
        </span>
        {limit && (
          <span className="push-right">
            {sessions.length} of {workspace.sessions.length} vehicles
          </span>
        )}
      </div>
    </div>
  );
}

export function VehicleTable({
  workspace,
  schedule,
}: {
  workspace: Workspace;
  schedule: Schedule | null;
}) {
  const [search, setSearch] = useState(""),
    [risksOnly, setRisksOnly] = useState(false),
    [selected, setSelected] = useState("");
  const rows = (schedule?.metrics.vehicles || []).filter(
    (v) =>
      v.vehicle_id.toLowerCase().includes(search.toLowerCase()) &&
      (!risksOnly || !v.target_met),
  );
  const records =
    schedule?.allocations.filter((a) => a.vehicle_id === selected) || [];
  return (
    <section className="panel">
      <PanelTitle
        eyebrow="VEHICLE READINESS"
        title="Departure targets & energy delivery"
        right={
          <span className="small-pill">
            {workspace.sessions.length} sessions
          </span>
        }
      />
      <div className="table-toolbar">
        <label className="search-box">
          <Search size={16} />
          <input
            aria-label="Search vehicles"
            placeholder="Search vehicle ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={risksOnly}
            onChange={(e) => setRisksOnly(e.target.checked)}
          />
          Show shortfalls only
        </label>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Vehicle</th>
              <th>Available UTC</th>
              <th>Required</th>
              <th>Delivered</th>
              <th>Shortfall</th>
              <th>Departure target</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.vehicle_id}>
                <td>
                  <button
                    className="vehicle-button"
                    onClick={() => setSelected(row.vehicle_id)}
                  >
                    {row.vehicle_id}
                    <ArrowRight size={12} />
                  </button>
                </td>
                <td>
                  {time(row.arrival_time)} – {time(row.departure_time)}
                </td>
                <td>{number(row.required_kwh, 2)} kWh</td>
                <td>{number(row.delivered_kwh, 2)} kWh</td>
                <td className={row.target_met ? "muted" : "warn-text"}>
                  {number(row.shortfall_kwh, 2)} kWh
                </td>
                <td>
                  <span
                    className={`target-pill ${row.target_met ? "" : "at-risk"}`}
                  >
                    {row.target_met ? (
                      <Check size={12} />
                    ) : (
                      <TriangleAlert size={12} />
                    )}
                    {row.target_met ? "Met" : "At risk"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && (
          <p className="empty-inline">No vehicles match this filter.</p>
        )}
      </div>
      {selected && (
        <div className="vehicle-inspector">
          <strong>
            {selected} · {records.length} allocation intervals
          </strong>
          <p className="muted">
            {records.length
              ? "Intervals use actual validated charging power."
              : "No charging is allocated to this vehicle."}
          </p>
          <div className="interval-list">
            {records.map((record, i) => (
              <span key={i}>
                {time(record.start_time)}–{time(record.end_time)} ·{" "}
                {record.charger_id} · {number(record.power_kw, 2)} kW
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

export function EventLog({
  workspace,
  disabled,
  onEvent,
  replay,
}: {
  workspace: Workspace;
  disabled: boolean;
  onEvent: () => void;
  replay: (event: SimEvent) => void;
}) {
  return (
    <section className="panel">
      <PanelTitle
        eyebrow="SIMULATION HISTORY"
        title="Every change, accounted for."
        right={
          <button className="text-button" disabled={disabled} onClick={onEvent}>
            Add event <ArrowRight size={15} />
          </button>
        }
      />
      {workspace.events.length === 0 ? (
        <p className="empty-inline">
          No disruptions yet. Add an event to exercise replanning.
        </p>
      ) : (
        <div className="event-list">
          {[...workspace.events].reverse().map((event) => (
            <div className="event-log-row" key={event.event_id}>
              <span className="event-icon">
                <RefreshCw size={16} />
              </span>
              <div>
                <strong>{event.type.replaceAll("_", " ")}</strong>
                <small>
                  {event.charger_id ||
                    `${number(event.add_eur_per_kwh || 0, 2)} EUR/kWh adjustment`}{" "}
                  · {time(event.start_time || event.time || workspace.now)} UTC
                </small>
                <code>{event.event_id}</code>
              </div>
              <button
                className="text-button"
                disabled={disabled}
                onClick={() => replay(event)}
              >
                Replay
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
