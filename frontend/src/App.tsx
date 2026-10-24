import {
  Check,
  CirclePlay,
  FileUp,
  LoaderCircle,
  PlugZap,
  TriangleAlert,
  X,
  Zap,
} from "lucide-react";
import type { Controller } from "./useWorkspace";
import { useWorkspace } from "./useWorkspace";
import { date } from "./format";
import { Layout } from "./components/Layout";
import { StatusStrip, Summary, WorkspaceView } from "./components/WorkspaceViews";
import { DemoGuide } from "./components/DemoGuide";
import { EventForm, Modal, StationForm, UploadForm } from "./components/Forms";

const titles = {
  overview: "Fleet charging planner",
  schedule: "Charging schedule",
  vehicles: "Vehicles & departure targets",
  agent: "AI operations",
};

function PageHeader({ ui }: { ui: Controller }) {
  return (
    <section className="page-heading">
      <div>
        <h1>{titles[ui.tab]}</h1>
        {ui.tab === "overview" && (
          <p className="value-statement">
            For fleet and depot managers: compare charging costs and departure targets, then test
            how a charger outage changes the plan.
          </p>
        )}
        <p className="scenario-meta">
          {ui.data
            ? `${ui.data.label} · ${date(ui.data.horizon_start)} · UTC`
            : "Loading simulation…"}
        </p>
      </div>
      <div className="heading-actions">
        <button
          className="button secondary"
          disabled={!!ui.busy}
          onClick={() => ui.load(false, true)}
        >
          <CirclePlay size={17} />
          Guided demo
        </button>
        <button
          className="button secondary"
          disabled={!!ui.busy || !ui.data}
          onClick={() => ui.set({ modal: "upload" })}
        >
          <FileUp size={17} />
          Upload CSV
        </button>
        <button
          className="button primary"
          disabled={!!ui.busy || !ui.data}
          onClick={() => ui.mutate("optimize")}
        >
          <Zap size={17} />
          {ui.data?.optimized ? "Re-optimize" : "Run optimizer"}
        </button>
      </div>
    </section>
  );
}

function Alert({
  message,
  error = false,
  onDismiss,
}: {
  message: string;
  error?: boolean;
  onDismiss?: () => void;
}) {
  if (!message) return null;
  const Icon = error ? TriangleAlert : Check;
  return (
    <div className={`alert ${error ? "error" : "success"}`} role={error ? "alert" : "status"}>
      <Icon size={18} />
      <span>{message}</span>
      {onDismiss && (
        <button aria-label="Dismiss message" onClick={onDismiss}>
          <X size={17} />
        </button>
      )}
    </div>
  );
}

function Dialogs({ ui }: { ui: Controller }) {
  if (!ui.modal || !ui.data) return null;
  const titles = {
    upload: "Bring your own charging sessions",
    station: "Configure your simulated station",
    event: "Simulate a change",
  };
  return (
    <Modal title={titles[ui.modal]} onClose={() => !ui.busy && ui.set({ modal: null })}>
      <Alert error message={ui.error} />
      {ui.modal === "upload" ? (
        <UploadForm disabled={!!ui.busy} onSubmit={ui.upload} />
      ) : ui.modal === "station" ? (
        <StationForm station={ui.data.station} disabled={!!ui.busy} onSubmit={ui.configure} />
      ) : (
        <EventForm workspace={ui.data} disabled={!!ui.busy} onSubmit={ui.simulate} />
      )}
    </Modal>
  );
}

function Content({ ui }: { ui: Controller }) {
  if (!ui.data)
    return ui.busy ? null : (
      <div className="empty-state">
        <PlugZap size={30} />
        <h2>Start a simulation</h2>
        <p>The API must be running to load a scenario.</p>
        <button className="button primary" onClick={() => ui.load()}>
          Try loading the demo
        </button>
      </div>
    );
  return (
    <>
      {ui.step !== null && (
        <DemoGuide
          step={ui.step}
          workspace={ui.data}
          busy={!!ui.busy}
          onNext={ui.nextStep}
          onClose={() => ui.set({ step: null })}
        />
      )}
      <StatusStrip ui={ui} />
      <Summary ui={ui} />
      <WorkspaceView ui={ui} />
    </>
  );
}

export default function App() {
  const ui = useWorkspace();
  return (
    <Layout ui={ui}>
      <PageHeader ui={ui} />
      {ui.busy && (
        <div className="busy-bar" role="status">
          <LoaderCircle className="spin" size={16} />
          {ui.busy}…
        </div>
      )}
      <Alert error message={ui.error} onDismiss={() => ui.set({ error: "" })} />
      <Alert message={ui.notice} onDismiss={() => ui.set({ notice: "" })} />
      <Content ui={ui} />
      <Dialogs ui={ui} />
    </Layout>
  );
}
