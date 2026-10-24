import { ArrowRight, Bot, Clock3, PlugZap, Settings2, ShieldCheck } from "lucide-react";
import type { Controller } from "../useWorkspace";
import { costDifference, money, number, time } from "../format";
import {
  EventLog,
  Metric,
  PanelTitle,
  PowerChart,
  StationPanel,
  Timeline,
  VehicleTable,
} from "./Dashboard";
import { ChatPanel } from "./AgentChat";
import { PlanningPanel } from "./PlanningPanel";

export function StatusStrip({ ui }: { ui: Controller }) {
  const data = ui.data!;
  return (
    <div className={`state-strip ${data.stale ? "state-stale" : ""}`}>
      <span>
        <span className="status-dot" />
        {data.stale
          ? "Previous plan · stale"
          : data.optimized
            ? "Optimized plan · independently validated"
            : "FCFS baseline ready · optimization pending"}
      </span>
      <span>
        <Clock3 size={14} />
        Simulation time {time(data.now)}
        <i />
        State {data.state_version} · Plan {data.schedule_version}
      </span>
    </div>
  );
}

export function Summary({ ui }: { ui: Controller }) {
  const data = ui.data!,
    measured = (data.optimized || data.baseline)?.metrics,
    comparison = data.comparison;
  const cards = [
    {
      title: "Charging cost",
      value: measured ? money(measured.cost_eur) : "—",
      detail:
        comparison?.cost_savings_eur != null
          ? costDifference(comparison.cost_savings_eur, comparison.cost_savings_percent)
          : comparison
            ? "Delivery differs; compare energy and cost"
            : "Run the optimizer for a comparison",
      positive: comparison?.cost_savings_eur != null && comparison.cost_savings_eur >= 0,
    },
    {
      title: "Peak station demand",
      value: number(measured?.peak_power_kw || 0),
      unit: "kW",
      detail: `${number(data.station.station_power_limit_kw)} kW station limit`,
    },
    {
      title: "Departure targets met",
      value: number(measured?.target_success_percent || 0),
      unit: "%",
      detail: `${data.analytics.vehicles} vehicles · ${number(data.analytics.total_energy_required_kwh)} kWh required`,
    },
    {
      title: "Unserved energy",
      value: number(measured?.unserved_kwh || 0, 2),
      unit: "kWh",
      detail:
        measured && measured.unserved_kwh <= 1e-5
          ? "All energy targets met by departure"
          : "Inspect vehicle details for shortfalls",
      warning: !!measured && measured.unserved_kwh > 1e-5,
    },
  ];
  return (
    <section className="metric-grid" aria-label="Schedule metrics">
      {cards.map((card) => (
        <Metric key={card.title} {...card} />
      ))}
    </section>
  );
}

function Operations({ ui }: { ui: Controller }) {
  const data = ui.data!;
  const actions = [
    {
      title: "Simulate a disruption",
      detail: "Outage, recovery, or price change",
      icon: PlugZap,
      run: () => ui.set({ modal: "event" }),
      disabled: false,
    },
    {
      title: "Advance simulation +1 hour",
      detail: "Preserve energy already delivered",
      icon: Clock3,
      run: ui.advance,
      disabled: data.stale || Date.parse(data.now) >= Date.parse(data.horizon_end),
    },
  ];
  return (
    <section className="panel operations-panel">
      <PanelTitle eyebrow="SIMULATION" title="Events & replanning" />
      <p className="muted">Compare policies under the same changed conditions.</p>
      {actions.map(({ title, detail, icon: Icon, run, disabled }) => (
        <button className="event-card" key={title} disabled={!!ui.busy || disabled} onClick={run}>
          <span className="event-icon">
            <Icon size={19} />
          </span>
          <span>
            <strong>{title}</strong>
            <small>{detail}</small>
          </span>
          <ArrowRight size={17} />
        </button>
      ))}
      <div className="recovery-stat">
        <span>Last plan calculation</span>
        <strong>{number(data.recovery_seconds || 0, 2)} s</strong>
      </div>
      <button className="text-button ai-link" onClick={() => ui.set({ tab: "agent" })}>
        <Bot size={16} />
        Ask Nemotron about the plan
        <ArrowRight size={15} />
      </button>
    </section>
  );
}

function Station({ ui }: { ui: Controller }) {
  return (
    <StationPanel
      workspace={ui.data!}
      disabled={!!ui.busy}
      onSettings={() => ui.set({ modal: "station" })}
    />
  );
}

function Overview({ ui }: { ui: Controller }) {
  const data = ui.data!;
  return (
    <>
      <div className="overview-grid">
        <section className="panel demand-panel">
          <PanelTitle
            eyebrow="ENERGY & CAPACITY"
            title="Station load & electricity price"
            right={<span className="small-pill">15-minute intervals</span>}
          />
          <PowerChart workspace={data} />
          <div className="chart-footer">
            {data.optimized && (
              <span>
                <span className="legend-line blue" />
                Optimized demand
              </span>
            )}
            <span>
              <span className="legend-line grey" />
              FCFS baseline
            </span>
            <span>
              <span className="legend-line amber-line" />
              Electricity price
            </span>
          </div>
        </section>
        <Station ui={ui} />
      </div>
      <div className="detail-grid">
        <section className="panel">
          <PanelTitle
            eyebrow="ALLOCATION"
            title="Charging schedule"
            right={
              <button className="text-button" onClick={() => ui.set({ tab: "schedule" })}>
                View schedule <ArrowRight size={15} />
              </button>
            }
          />
          <Timeline workspace={data} schedule={data.optimized || data.baseline} limit={8} />
        </section>
        <Operations ui={ui} />
      </div>
      <PlanningPanel
        key={`${data.workspace_id}-${data.state_version}-${data.schedule_version}`}
        ui={ui}
      />
    </>
  );
}

function ScheduleView({ ui }: { ui: Controller }) {
  const data = ui.data!,
    active = data.optimized || data.baseline;
  return (
    <>
      <section className="panel">
        <PanelTitle
          eyebrow="VALIDATED ALLOCATIONS"
          title="Charging timeline"
          right={
            <span className="small-pill">
              {active?.solver_status} · {number(active?.runtime_seconds || 0, 2)} s
            </span>
          }
        />
        <Timeline workspace={data} schedule={active} />
      </section>
      <div className="below-grid">
        <Station ui={ui} />
        <EventLog
          workspace={data}
          disabled={!!ui.busy}
          onEvent={() => ui.set({ modal: "event" })}
          replay={ui.simulate}
        />
      </div>
    </>
  );
}

function AgentView({ ui }: { ui: Controller }) {
  const entries = [
    {
      icon: ShieldCheck,
      title: "Validated state",
      detail: "Reads the same schedule, risks, and measured metrics shown in this workspace.",
    },
    {
      icon: Settings2,
      title: "Controlled tools",
      detail: "Enable simulation changes to let the agent optimize or apply an event.",
    },
    {
      icon: PlugZap,
      title: "Simulation only",
      detail: "No physical charging equipment is connected.",
    },
  ];
  return (
    <div className="agent-layout">
      <ChatPanel workspace={ui.data!} messages={ui.messages} busy={!!ui.busy} onSend={ui.chat} />
      <section className="panel agent-context">
        <PanelTitle eyebrow="ASSISTANT CONTEXT" title="Grounded in your schedule" />
        {entries.map(({ icon: Icon, title, detail }) => (
          <div className="context-item" key={title}>
            <Icon size={20} />
            <div>
              <strong>{title}</strong>
              <p>{detail}</p>
            </div>
          </div>
        ))}
        <div className="agent-model">
          <span>Model</span>
          <code>{ui.data!.agent.model || "Not configured"}</code>
        </div>
      </section>
    </div>
  );
}

export function WorkspaceView({ ui }: { ui: Controller }) {
  if (ui.tab === "overview") return <Overview ui={ui} />;
  if (ui.tab === "schedule") return <ScheduleView ui={ui} />;
  if (ui.tab === "agent") return <AgentView ui={ui} />;
  return <VehicleTable workspace={ui.data!} schedule={ui.data!.optimized || ui.data!.baseline} />;
}
