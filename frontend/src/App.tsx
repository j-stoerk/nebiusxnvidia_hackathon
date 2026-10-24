import { useEffect, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  BatteryCharging,
  Bot,
  Check,
  ChevronDown,
  Clock3,
  FileUp,
  Gauge,
  LayoutDashboard,
  ListFilter,
  LoaderCircle,
  PlugZap,
  CirclePlay,
  RefreshCw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  X,
  Zap,
} from "lucide-react";
import { api, createWorkspace } from "./api";
import type { ChatMessage, Reply, SimEvent, Workspace } from "./types";
import { costDifference, date, money, number, time } from "./format";
import {
  Metric,
  PanelTitle,
  PowerChart,
  StationPanel,
  Timeline,
  VehicleTable,
  EventLog,
} from "./components/Dashboard";
import { ChatPanel } from "./components/AgentChat";
import { Modal, UploadForm, StationForm, EventForm } from "./components/Forms";
import { DemoGuide } from "./components/DemoGuide";

type Tab = "overview" | "schedule" | "vehicles" | "agent";
const nav = [
  { id: "overview", name: "Overview", icon: LayoutDashboard },
  { id: "schedule", name: "Charging schedule", icon: BatteryCharging },
  { id: "vehicles", name: "Vehicles & risks", icon: ListFilter },
  { id: "agent", name: "AI operations", icon: Bot },
] as const;

function App() {
  const [data, setData] = useState<Workspace | null>(null);
  const [busy, setBusy] = useState<string | null>("Loading workspace");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState<Tab>("overview");
  const [modal, setModal] = useState<"upload" | "station" | "event" | null>(
    null,
  );
  const [conversation, setConversation] = useState<ChatMessage[]>([]);
  const [demoStep, setDemoStep] = useState<number | null>(() =>
    new URLSearchParams(location.search).get("demo") === "1" ? 0 : null,
  );
  const [demoOutage, setDemoOutage] = useState<SimEvent | null>(null);

  useEffect(() => {
    let active = true;
    const cached =
      new URLSearchParams(location.search).get("demo") === "1"
        ? null
        : sessionStorage.getItem("chargewise-workspace");
    (cached
      ? api<Workspace>(`/workspaces/${cached}`).catch(() => createWorkspace())
      : createWorkspace()
    )
      .then((next) => {
        if (active) {
          setData(next);
          sessionStorage.setItem("chargewise-workspace", next.workspace_id);
        }
      })
      .catch((reason) => {
        if (active)
          setError(
            reason.message ||
              "Cannot reach the API. Start the FastAPI backend.",
          );
      })
      .finally(() => {
        if (active) setBusy(null);
      });
    return () => {
      active = false;
    };
  }, []);

  async function action(
    operation: () => Promise<Workspace>,
    label: string,
    preserveGuide = false,
  ) {
    if (!preserveGuide) setDemoStep(null);
    setBusy(label);
    setError("");
    setNotice("");
    try {
      const next = await operation();
      setData(next);
      sessionStorage.setItem("chargewise-workspace", next.workspace_id);
      if (next.last_error) setError(next.last_error);
      return next;
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Something went wrong",
      );
      if (data) {
        try {
          setData(await api<Workspace>(`/workspaces/${data.workspace_id}`));
        } catch {
          /* Keep the current view; error remains visible. */
        }
      }
    } finally {
      setBusy(null);
    }
  }
  const path = (suffix: string) =>
    `/workspaces/${data!.workspace_id}/${suffix}`;
  const version = () => ({ expected_version: data!.state_version });
  const active = data?.optimized || data?.baseline;
  const totals = active?.metrics;

  async function loadDemo(stress: boolean, guided = false) {
    const next = await action(
      () => createWorkspace(stress ? "stress" : "normal"),
      "Loading scenario",
    );
    if (next) {
      setDemoStep(guided ? 0 : null);
      setDemoOutage(null);
      setConversation([]);
      setNotice(
        stress
          ? "100-session stress scenario loaded. Impossible targets will be reported as shortfall."
          : "50-vehicle scenario loaded. Run the optimizer to compare schedules.",
      );
    }
  }

  async function nextDemoStep() {
    if (!data || demoStep === null) return;
    if (demoStep === 4) {
      setDemoStep(null);
      setTab("schedule");
      return;
    }
    if (demoStep === 0) {
      const result = await action(
        () => api<Workspace>(path("optimize"), version()),
        "Optimizing the demo",
        true,
      );
      if (result && !result.stale) setDemoStep(1);
      return;
    }
    const previousVersion = data.state_version;
    const result = await action(
      async () => {
        const fixtures = await api<{ scenarios: Record<string, SimEvent[]> }>(
          "/demo/scenarios",
        );
        const event =
          demoStep === 1
            ? fixtures.scenarios.charger_outage[0]
            : demoStep === 2
              ? fixtures.scenarios.price_spike[0]
              : demoOutage || fixtures.scenarios.charger_outage[0];
        const changed = await api<Workspace>(path("events"), {
          ...version(),
          event,
        });
        if (demoStep === 1) setDemoOutage(event);
        return changed;
      },
      demoStep === 1
        ? "Simulating the charger outage"
        : demoStep === 2
          ? "Applying the price spike"
          : "Checking duplicate event delivery",
      true,
    );
    if (result && !result.stale) {
      setDemoStep(demoStep + 1);
      if (demoStep === 3)
        setNotice(
          `Duplicate event ignored. State ${previousVersion} remains ${result.state_version}.`,
        );
    }
  }

  async function sendChat(message: string, allowChanges: boolean) {
    if (!data) return;
    if (allowChanges) setDemoStep(null);
    setConversation((previous) => [
      ...previous,
      { role: "user", text: message },
    ]);
    setBusy("Nemotron is working");
    setError("");
    try {
      const result = await api<{ reply: Reply; workspace: Workspace }>(
        path("chat"),
        { ...version(), message, allow_changes: allowChanges },
      );
      setData(result.workspace);
      setConversation((previous) => [
        ...previous,
        { role: "assistant", text: result.reply.message, reply: result.reply },
      ]);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not contact Nemotron",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          href="#"
          className="brand"
          onClick={(event) => {
            event.preventDefault();
            setTab("overview");
          }}
        >
          <span className="brand-symbol">
            <Zap size={24} fill="currentColor" />
          </span>
          <span>
            ChargeWise<span className="brand-ai">AI</span>
          </span>
        </a>
        <div className="workspace-pill">
          <span className="workspace-avatar">CW</span>
          <span>
            Demo workspace<small>EV charging operations</small>
          </span>
          <ChevronDown size={15} />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {nav.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${tab === item.id ? "selected" : ""}`}
              onClick={() => setTab(item.id)}
            >
              <item.icon size={18} />
              {item.name}
              {item.id === "agent" && (
                <span className="nav-new" aria-hidden="true">
                  AI
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="nav-label scenario-label">DEMO SCENARIOS</div>
        <button
          className="scenario-link"
          disabled={!!busy}
          onClick={() => loadDemo(false)}
        >
          <span className="scenario-dot" />
          50 vehicles · normal day
        </button>
        <button
          className="scenario-link"
          disabled={!!busy}
          onClick={() => loadDemo(true)}
        >
          <span className="scenario-dot amber" />
          100 sessions · stress test
        </button>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <ShieldCheck size={19} />
            <strong>Every plan gets checked.</strong>
            <p>
              Physical limits are validated before a new schedule is activated.
            </p>
          </div>
          <a href="/api/demo/sessions" className="sidebar-download">
            <ArrowDownToLine size={16} /> Download sample CSV
          </a>
          <div className="sidebar-footer">
            <span className="status-dot" />
            Simulation environment<span>v0.1</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span>{" "}
            <strong>{nav.find((item) => item.id === tab)?.name}</strong>
          </div>
          <div className="topbar-right">
            <select
              className="mobile-scenario"
              aria-label="Load demo scenario"
              defaultValue=""
              disabled={!!busy}
              onChange={(event) => {
                const value = event.target.value;
                event.target.value = "";
                if (value) loadDemo(value === "stress");
              }}
            >
              <option value="" disabled>
                Load demo…
              </option>
              <option value="normal">50 vehicles</option>
              <option value="stress">100-session stress</option>
            </select>
            <span className="environment">
              <span className="status-dot" /> SIMULATION
            </span>
            <span className="avatar">CW</span>
          </div>
        </header>
        <main>
          <section className="page-heading">
            <div>
              <div className="eyebrow">CHARGING OPERATIONS</div>
              <h1>
                {tab === "overview"
                  ? "A smarter day of charging."
                  : tab === "schedule"
                    ? "Every vehicle. Every interval."
                    : tab === "vehicles"
                      ? "Know who’s ready to go."
                      : "Your charging operations copilot."}
              </h1>
              <p>
                {data
                  ? `${data.label} · ${date(data.horizon_start)} · All times UTC`
                  : "Loading your simulation workspace…"}
              </p>
            </div>
            <div className="heading-actions">
              <button
                className="button secondary"
                disabled={!!busy}
                onClick={async () => {
                  await loadDemo(false, true);
                  setTab("overview");
                }}
              >
                <CirclePlay size={17} />
                Guided demo
              </button>
              <button
                className="button secondary"
                disabled={!!busy || !data}
                onClick={() => setModal("upload")}
              >
                <FileUp size={17} />
                Upload CSV
              </button>
              <button
                className="button primary"
                disabled={!!busy || !data}
                onClick={() =>
                  action(
                    () => api<Workspace>(path("optimize"), version()),
                    "Optimizing schedule",
                  )
                }
              >
                <Zap size={17} />
                {data?.optimized ? "Re-optimize" : "Run optimizer"}
              </button>
            </div>
          </section>

          {busy && (
            <div className="busy-bar" role="status">
              <LoaderCircle className="spin" size={16} />
              {busy}…
            </div>
          )}
          {error && (
            <div className="alert error" role="alert">
              <TriangleAlert size={18} />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={17} />
              </button>
            </div>
          )}
          {notice && (
            <div className="alert success" role="status">
              <Check size={18} />
              <span>{notice}</span>
              <button aria-label="Dismiss notice" onClick={() => setNotice("")}>
                <X size={17} />
              </button>
            </div>
          )}
          {!data && !busy && (
            <div className="empty-state">
              <PlugZap size={30} />
              <h2>Start your charging workspace</h2>
              <p>The API needs to be available to load a scenario.</p>
              <button
                className="button primary"
                onClick={() => loadDemo(false)}
              >
                Try loading the demo
              </button>
            </div>
          )}
          {data && (
            <>
              {demoStep !== null && (
                <DemoGuide
                  step={demoStep}
                  workspace={data}
                  busy={!!busy}
                  onNext={nextDemoStep}
                  onClose={() => setDemoStep(null)}
                />
              )}
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
              <section className="metric-grid" aria-label="Schedule metrics">
                <Metric
                  title="Charging cost"
                  value={totals ? money(totals.cost_eur) : "—"}
                  icon={<span className="euro">€</span>}
                  detail={
                    data.comparison?.cost_savings_eur != null
                      ? costDifference(
                          data.comparison.cost_savings_eur,
                          data.comparison.cost_savings_percent,
                        )
                      : data.comparison
                        ? "Energy delivery differs; costs are not savings"
                        : "Run optimization for a measured comparison"
                  }
                  positive={
                    data.comparison?.cost_savings_eur != null &&
                    data.comparison.cost_savings_eur >= 0
                  }
                />
                <Metric
                  title="Peak station demand"
                  value={totals ? number(totals.peak_power_kw) : "—"}
                  unit="kW"
                  icon={<Gauge size={20} />}
                  detail={`${number(data.station.station_power_limit_kw)} kW station limit`}
                />
                <Metric
                  title="Departure targets met"
                  value={totals ? number(totals.target_success_percent) : "—"}
                  unit="%"
                  icon={<BatteryCharging size={20} />}
                  detail={`${data.analytics.vehicles} vehicles · ${number(data.analytics.total_energy_required_kwh)} kWh required`}
                />
                <Metric
                  title="Unserved energy"
                  value={totals ? number(totals.unserved_kwh, 2) : "—"}
                  unit="kWh"
                  icon={<Activity size={20} />}
                  detail={
                    totals && totals.unserved_kwh <= 1e-5
                      ? "All energy targets met by departure"
                      : "Shortfalls remain visible in vehicle details"
                  }
                  warning={!!totals && totals.unserved_kwh > 1e-5}
                />
              </section>

              {tab === "overview" && (
                <>
                  <div className="overview-grid">
                    <section className="panel demand-panel">
                      <PanelTitle
                        eyebrow="ENERGY & CAPACITY"
                        title="Better timing. Same physical limits."
                        right={
                          <span className="small-pill">15-minute view</span>
                        }
                      />
                      <PowerChart workspace={data} />
                      <div className="chart-footer">
                        <span>
                          <span className="legend-line green" />
                          Optimized demand
                        </span>
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
                    <StationPanel
                      workspace={data}
                      onSettings={() => setModal("station")}
                      disabled={!!busy}
                    />
                  </div>
                  <div className="detail-grid">
                    <section className="panel">
                      <PanelTitle
                        eyebrow="CHARGING PLAN"
                        title="Room for every departure."
                        right={
                          <button
                            className="text-button"
                            onClick={() => setTab("schedule")}
                          >
                            View schedule <ArrowRight size={15} />
                          </button>
                        }
                      />
                      <Timeline
                        workspace={data}
                        schedule={active || null}
                        limit={8}
                      />
                    </section>
                    <section className="panel operations-panel">
                      <PanelTitle
                        eyebrow="WHAT IF?"
                        title="Plans change. Stay ready."
                      />
                      <p className="muted">
                        Introduce a disruption, then compare a new validated
                        schedule with the same-state baseline.
                      </p>
                      <button
                        className="event-card"
                        disabled={!!busy}
                        onClick={() => setModal("event")}
                      >
                        <span className="event-icon">
                          <PlugZap size={19} />
                        </span>
                        <span>
                          <strong>Simulate a disruption</strong>
                          <small>Outage, recovery, or price change</small>
                        </span>
                        <ArrowRight size={17} />
                      </button>
                      <button
                        className="event-card"
                        disabled={
                          !!busy ||
                          Date.parse(data.now) >=
                            Date.parse(data.horizon_end) ||
                          data.stale
                        }
                        onClick={() =>
                          action(
                            () =>
                              api<Workspace>(path("advance"), {
                                ...version(),
                                time: new Date(
                                  Math.min(
                                    Date.parse(data.now) + 3600000,
                                    Date.parse(data.horizon_end),
                                  ),
                                ).toISOString(),
                              }),
                            "Advancing simulation and replanning",
                          )
                        }
                      >
                        <span className="event-icon subtle">
                          <Clock3 size={19} />
                        </span>
                        <span>
                          <strong>Advance simulation +1 hour</strong>
                          <small>Preserve energy already delivered</small>
                        </span>
                        <ArrowRight size={17} />
                      </button>
                      <div className="recovery-stat">
                        <span>Last plan calculation</span>
                        <strong>
                          {data.recovery_seconds == null
                            ? "—"
                            : `${number(data.recovery_seconds, 2)} s`}
                        </strong>
                      </div>
                      <button
                        className="text-button ai-link"
                        onClick={() => setTab("agent")}
                      >
                        <Sparkles size={16} />
                        Ask Nemotron about the plan
                        <ArrowRight size={15} />
                      </button>
                    </section>
                  </div>
                  {data.analytics.warnings.length > 0 && (
                    <div className="alert warning">
                      <TriangleAlert size={18} />
                      <span>
                        {data.analytics.warnings.length} vehicle target(s)
                        cannot fit within individual availability or compatible
                        capacity.{" "}
                        <button
                          className="inline-link"
                          onClick={() => setTab("vehicles")}
                        >
                          Review risks
                        </button>
                      </span>
                    </div>
                  )}
                </>
              )}
              {tab === "schedule" && (
                <>
                  <section className="panel">
                    <PanelTitle
                      eyebrow="VALIDATED ALLOCATIONS"
                      title="Charging timeline"
                      right={
                        <span className="small-pill">
                          {active?.solver_status} ·{" "}
                          {number(active?.runtime_seconds || 0, 2)} s
                        </span>
                      }
                    />
                    <Timeline workspace={data} schedule={active || null} />
                  </section>
                  <div className="below-grid">
                    <StationPanel
                      workspace={data}
                      onSettings={() => setModal("station")}
                      disabled={!!busy}
                    />
                    <EventLog
                      workspace={data}
                      disabled={!!busy}
                      onEvent={() => setModal("event")}
                      replay={async (event) => {
                        const next = await action(
                          () =>
                            api<Workspace>(path("events"), {
                              ...version(),
                              event,
                            }),
                          "Replaying the same event",
                        );
                        if (next)
                          setNotice(
                            `Duplicate ${event.event_id} ignored. State remains ${next.state_version}.`,
                          );
                      }}
                    />
                  </div>
                </>
              )}
              {tab === "vehicles" && (
                <VehicleTable workspace={data} schedule={active || null} />
              )}
              {tab === "agent" && (
                <div className="agent-layout">
                  <ChatPanel
                    workspace={data}
                    messages={conversation}
                    busy={!!busy}
                    onSend={sendChat}
                  />
                  <section className="panel agent-context">
                    <PanelTitle
                      eyebrow="GROUNDED IN YOUR PLAN"
                      title="One source of truth."
                    />
                    <div className="context-item">
                      <ShieldCheck size={20} />
                      <div>
                        <strong>Validated schedules</strong>
                        <p>
                          Nemotron reads the same state, intervals, risks, and
                          metrics shown here.
                        </p>
                      </div>
                    </div>
                    <div className="context-item">
                      <Settings2 size={20} />
                      <div>
                        <strong>Controlled actions</strong>
                        <p>
                          Enable simulation changes to let the agent call
                          optimization or event tools.
                        </p>
                      </div>
                    </div>
                    <div className="context-item">
                      <PlugZap size={20} />
                      <div>
                        <strong>Simulation only</strong>
                        <p>
                          These actions change this workspace. No physical
                          charger is connected.
                        </p>
                      </div>
                    </div>
                    <div className="agent-model">
                      <span>Model</span>
                      <code>{data.agent.model || "Not configured"}</code>
                    </div>
                  </section>
                </div>
              )}
              <footer className="main-footer">
                <span>
                  <Zap size={14} />
                  ChargeWise AI · Simulated charging operations
                </span>
                <a href="/docs" target="_blank" rel="noreferrer">
                  API documentation <ArrowRight size={13} />
                </a>
              </footer>
            </>
          )}
        </main>
      </div>

      {modal && data && (
        <Modal
          title={
            modal === "upload"
              ? "Bring your own charging sessions"
              : modal === "station"
                ? "Configure your simulated station"
                : "Simulate a change"
          }
          onClose={() => !busy && setModal(null)}
        >
          {error && (
            <div className="alert error" role="alert">
              <TriangleAlert size={18} />
              <span>{error}</span>
            </div>
          )}
          {modal === "upload" && (
            <UploadForm
              disabled={!!busy}
              onSubmit={async (form) => {
                form.append("expected_version", String(data.state_version));
                const next = await action(
                  () => api<Workspace>(path("upload"), form),
                  "Validating CSV and calculating schedules",
                );
                if (next && !next.stale) {
                  setModal(null);
                  setConversation([]);
                  setNotice(
                    "CSV validated. Baseline and optimized schedules are ready.",
                  );
                }
              }}
            />
          )}
          {modal === "station" && (
            <StationForm
              station={data.station}
              disabled={!!busy}
              onSubmit={async (station) => {
                const next = await action(
                  () =>
                    api<Workspace>(
                      path("station"),
                      { ...version(), station },
                      "PUT",
                    ),
                  "Updating station and replanning",
                );
                if (next && !next.stale) setModal(null);
              }}
            />
          )}
          {modal === "event" && (
            <EventForm
              workspace={data}
              disabled={!!busy}
              onSubmit={async (event) => {
                const next = await action(
                  () => api<Workspace>(path("events"), { ...version(), event }),
                  "Applying event and replanning",
                );
                if (next) {
                  setModal(null);
                  if (!next.stale)
                    setNotice(
                      `Event applied. Plan ${next.schedule_version} passed all physical constraint checks.`,
                    );
                }
              }}
            />
          )}
        </Modal>
      )}
    </div>
  );
}

export default App;
