import { ArrowRight, Check, CirclePlay, LoaderCircle, X } from "lucide-react";
import type { Workspace } from "../types";

// The guide drives real API calls; all financial/energy results stay in Summary.
const steps = [
  [
    "Baseline",
    "Review the first-come-first-served baseline",
    "50 simulated vehicles, ten chargers, and an 80 kW site. Optimize this same scenario to compare results.",
    "Optimize this plan",
  ],
  [
    "Optimize",
    "Compare energy and electricity cost",
    "Both schedules are checked against the physical limits. Savings are shown only when delivered energy matches.",
    "Simulate charger outage",
  ],
  [
    "Outage",
    "Replan around a charger outage",
    "CH-01 is unavailable from 09:00 to 12:00 UTC. Both schedules now include that outage.",
    "Apply the price change",
  ],
  [
    "Price change",
    "Respond to a price increase",
    "The 15:00–18:00 price has increased by 0.20 EUR/kWh. Inspect the recalculated charging plan below.",
    "Replay the same outage",
  ],
  [
    "Replay",
    "Verify duplicate event handling",
    "Replaying the original event ID leaves state and schedule versions unchanged. The final plan is ready to inspect.",
    "Explore the final schedule",
  ],
];

function Progress({ step }: { step: number }) {
  return (
    <ol className="demo-progress grid grid-cols-5 border-t px-4 py-3">
      {steps.map(([name], index) => (
        <li
          key={name}
          aria-current={step === index ? "step" : undefined}
          data-complete={index < step || step === 4}
        >
          <span className="step-number">
            {index < step || step === 4 ? <Check size={12} /> : index + 1}
          </span>
          <span className="hidden sm:inline">{name}</span>
        </li>
      ))}
    </ol>
  );
}

export function DemoGuide({
  step,
  workspace,
  busy,
  onNext,
  onClose,
}: {
  step: number;
  workspace: Workspace;
  busy: boolean;
  onNext: () => void;
  onClose: () => void;
}) {
  const [, title, description, button] = steps[step];
  return (
    <section
      aria-label="Guided demo"
      data-demo-step={step}
      className="demo-guide mb-5 overflow-hidden rounded-lg border"
    >
      <header className="flex items-center justify-between border-b px-5 py-3">
        <span>
          <CirclePlay size={16} />
          <strong>Guided demo</strong>
          <small>Step {step + 1} of 5</small>
        </span>
        <button
          className="icon-button"
          aria-label="Exit guided demo"
          disabled={busy}
          onClick={onClose}
        >
          <X size={16} />
        </button>
      </header>
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <button className="button primary" disabled={busy || workspace.stale} onClick={onNext}>
          {busy ? <LoaderCircle className="spin" size={16} /> : <ArrowRight size={16} />}
          {button}
        </button>
      </div>
      <Progress step={step} />
    </section>
  );
}
