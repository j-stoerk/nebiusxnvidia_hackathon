import type { ReactNode } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  BatteryCharging,
  Bot,
  LayoutDashboard,
  ListFilter,
  ShieldCheck,
  Zap,
} from "lucide-react";
import type { Controller } from "../useWorkspace";

const navigation = [
  { id: "overview", name: "Overview", icon: LayoutDashboard },
  { id: "schedule", name: "Charging schedule", icon: BatteryCharging },
  { id: "vehicles", name: "Vehicles & risks", icon: ListFilter },
  { id: "agent", name: "AI operations", icon: Bot },
] as const;

function Sidebar({ ui }: { ui: Controller }) {
  return (
    <aside className="sidebar">
      <a
        href="#"
        className="brand"
        onClick={(event) => {
          event.preventDefault();
          ui.set({ tab: "overview" });
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
      </div>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation">
        {navigation.map(({ id, name, icon: Icon }) => (
          <button
            key={id}
            className={`nav-item ${ui.tab === id ? "selected" : ""}`}
            onClick={() => ui.set({ tab: id })}
          >
            <Icon size={18} />
            {name}
            {id === "agent" && (
              <span className="nav-new" aria-hidden="true">
                AI
              </span>
            )}
          </button>
        ))}
      </nav>
      <div className="nav-label scenario-label">DEMO SCENARIOS</div>
      {[false, true].map((stress) => (
        <button
          key={String(stress)}
          className="scenario-link"
          disabled={!!ui.busy}
          onClick={() => ui.load(stress)}
        >
          <span className={`scenario-dot ${stress ? "amber" : ""}`} />
          {stress ? "100 sessions · stress test" : "50 vehicles · normal day"}
        </button>
      ))}
      <div className="sidebar-bottom">
        <div className="sidebar-note">
          <ShieldCheck size={19} />
          <strong>Every plan gets checked.</strong>
          <p>Physical limits are validated before a new schedule is activated.</p>
        </div>
        <a href="/api/demo/sessions" className="sidebar-download">
          <ArrowDownToLine size={16} />
          Download sample CSV
        </a>
        <div className="sidebar-footer">
          <span className="status-dot" />
          Simulation environment<span>v0.1</span>
        </div>
      </div>
    </aside>
  );
}

function Topbar({ ui }: { ui: Controller }) {
  return (
    <header className="topbar">
      <div className="breadcrumb">
        Workspace <span>/</span>
        <strong>{navigation.find((item) => item.id === ui.tab)?.name}</strong>
      </div>
      <div className="topbar-right">
        <select
          className="mobile-scenario"
          aria-label="Load demo scenario"
          defaultValue=""
          disabled={!!ui.busy}
          onChange={(event) => {
            const value = event.target.value;
            event.target.value = "";
            if (value) ui.load(value === "stress");
          }}
        >
          <option value="" disabled>
            Load demo…
          </option>
          <option value="normal">50 vehicles</option>
          <option value="stress">100-session stress</option>
        </select>
        <span className="environment">
          <span className="status-dot" />
          SIMULATION
        </span>
        <span className="avatar">CW</span>
      </div>
    </header>
  );
}

export function Layout({ ui, children }: { ui: Controller; children: ReactNode }) {
  return (
    <div className="app-shell">
      <Sidebar ui={ui} />
      <div className="main-shell">
        <Topbar ui={ui} />
        <main>
          {children}
          <footer className="main-footer">
            <span>
              <Zap size={14} />
              ChargeWise AI · Simulated charging operations
            </span>
            <a href="/docs" target="_blank" rel="noreferrer">
              API documentation <ArrowRight size={13} />
            </a>
          </footer>
        </main>
      </div>
    </div>
  );
}
