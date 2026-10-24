import type { ReactNode } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  BatteryCharging,
  Bot,
  LayoutDashboard,
  ListFilter,
} from "lucide-react";
import brand from "../assets/brand.svg";
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
        aria-label="ChargeWise home"
        onClick={(event) => {
          event.preventDefault();
          ui.set({ tab: "overview" });
        }}
      >
        <img src={brand} width="32" height="32" alt="" />
        <span>chargewise</span>
      </a>
      <div className="brand-caption">Fleet charging, planned.</div>
      <nav aria-label="Main navigation">
        {navigation.map(({ id, name, icon: Icon }) => (
          <button
            key={id}
            className={`nav-item ${ui.tab === id ? "selected" : ""}`}
            aria-current={ui.tab === id ? "page" : undefined}
            onClick={() => ui.set({ tab: id })}
          >
            <Icon size={18} />
            {name}
          </button>
        ))}
      </nav>
      <div className="nav-label scenario-label">Try a scenario</div>
      {[false, true].map((stress) => (
        <button
          key={String(stress)}
          className="scenario-link"
          disabled={!!ui.busy}
          onClick={() => ui.load(stress)}
        >
          <span className={`scenario-dot ${stress ? "amber" : ""}`} />
          {stress ? "100 sessions · stress test" : "50 sessions · vehicle moves"}
        </button>
      ))}
      <button className="scenario-link" disabled={!!ui.busy} onClick={() => ui.load("capacity")}>
        <span className="scenario-dot" />4 vans · depot day
      </button>
      <div className="sidebar-bottom">
        <a href="/api/demo/sessions" className="sidebar-download">
          <ArrowDownToLine size={16} />
          Download sample CSV
        </a>
        <div className="sidebar-footer">
          <span className="status-dot" />
          Simulation environment
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
            if (value) ui.load(value === "capacity" ? "capacity" : value === "stress");
          }}
        >
          <option value="" disabled>
            Load demo…
          </option>
          <option value="normal">50 sessions · moves</option>
          <option value="stress">100-session stress</option>
          <option value="capacity">4 vans · depot day</option>
        </select>
        <span className="environment">
          <span className="status-dot" />
          Demo workspace
        </span>
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
            <span>ChargeWise · Simulated charging operations</span>
            <a href="/docs" target="_blank" rel="noreferrer">
              API documentation <ArrowRight size={13} />
            </a>
          </footer>
        </main>
      </div>
    </div>
  );
}
