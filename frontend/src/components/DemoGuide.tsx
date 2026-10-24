import {
  ArrowRight,
  Check,
  CirclePlay,
  LoaderCircle,
  ShieldCheck,
  X,
} from "lucide-react";
import type { Workspace } from "../types";
import { money, number } from "../format";

const steps = ["Baseline", "Optimize", "Outage", "Price change", "Replay"];
const titles = [
  "Start with a real baseline calculation.",
  "Same energy. A better charging plan.",
  "One charger goes down. The plan adapts.",
  "Prices change. Charging moves with them.",
  "One event, applied exactly once.",
];
const descriptions = [
  "50 simulated vehicles, ten chargers, and an 80 kW station. This first-come-first-served plan gives you a measured starting point.",
  "The optimizer prioritizes energy targets, then electricity cost. The dashboard below shows the actual comparison, checked against physical limits.",
  "Charger CH-01 is unavailable from 09:00 to 12:00 UTC. Both plans have been recalculated under that outage, preserving the same constraints.",
  "A 0.20 EUR/kWh increase from 15:00 to 18:00 UTC is now part of the scenario. These are recomputed results, not a scripted savings claim.",
  "The exact same outage was delivered again. Its ID was recognized, so no event or state change was applied twice. Explore the final schedule or ask Nemotron about it.",
];
const buttons = [
  "Optimize this plan",
  "Simulate charger outage",
  "Apply the price change",
  "Replay the same outage",
  "Explore the final schedule",
];

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
  const active = workspace.optimized || workspace.baseline;
  return (
    <section
      aria-label="Guided demo"
      data-demo-step={step}
      className="mb-5 overflow-hidden rounded-xl border border-[#dce8cf] bg-[#eef5e7]"
    >
      <div className="flex items-center justify-between gap-3 border-b border-[#dce8cf] px-5 py-3">
        <span className="flex items-center gap-2 text-[10px] font-semibold tracking-[1.5px] text-[#688052]">
          <CirclePlay size={15} /> GUIDED DEMO{" "}
          <span className="ml-2 font-normal tracking-normal opacity-70">
            Step {step + 1} of 5
          </span>
        </span>
        <button
          aria-label="Exit guided demo"
          className="rounded p-1 text-[#7b9069] hover:bg-[#e1ecd6]"
          disabled={busy}
          onClick={onClose}
        >
          <X size={16} />
        </button>
      </div>
      <div className="grid gap-6 p-5 md:p-6 xl:grid-cols-[1.8fr_1fr]">
        <div>
          <h2 className="m-0 text-[21px] font-medium tracking-[-0.5px] text-[#254a31]">
            {step === 1 && !workspace.comparison?.equal_delivered_energy
              ? "Compare energy and cost together."
              : titles[step]}
          </h2>
          <p className="mt-3 max-w-xl text-[12px] leading-[1.8] text-[#687e56]">
            {descriptions[step]}
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-4">
            <button
              className="button primary"
              disabled={busy || workspace.stale}
              onClick={onNext}
            >
              {busy ? (
                <LoaderCircle className="spin" size={16} />
              ) : step === 4 ? (
                <Check size={16} />
              ) : (
                <ArrowRight size={16} />
              )}
              {buttons[step]}
            </button>
            <span className="flex items-center gap-1.5 text-[10px] text-[#769260]">
              <ShieldCheck size={14} />
              {workspace.stale
                ? "Replan needs attention"
                : "Actual results · independently validated"}
            </span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 self-center">
          <div className="rounded-lg border border-[#dfe8d4] bg-white/70 p-4">
            <span className="text-[9px] text-[#879674]">CURRENT PLAN</span>
            <strong className="mt-2 block text-[25px] font-medium tracking-tight text-[#32513a]">
              {active ? money(active.metrics.cost_eur) : "—"}
            </strong>
            <span className="mt-2 block text-[9px] text-[#81956c]">
              {active
                ? `${number(active.metrics.delivered_kwh, 1)} kWh delivered`
                : "Awaiting calculation"}
            </span>
          </div>
          <div className="rounded-lg border border-[#dfe8d4] bg-white/70 p-4">
            <span className="text-[9px] text-[#879674]">TARGETS MET</span>
            <strong className="mt-2 block text-[25px] font-medium tracking-tight text-[#32513a]">
              {active
                ? `${number(active.metrics.target_success_percent)}%`
                : "—"}
            </strong>
            <span className="mt-2 block text-[9px] text-[#81956c]">
              {workspace.agent.configured
                ? "Nemotron configured"
                : "AI not connected · scheduling works"}
            </span>
          </div>
        </div>
      </div>
      <ol className="m-0 grid list-none grid-cols-5 border-t border-[#dce8cf] bg-white/30 px-4 py-3">
        {steps.map((label, index) => (
          <li
            key={label}
            className="flex items-center justify-center gap-2 text-[10px]"
            aria-current={index === step ? "step" : undefined}
          >
            <span
              className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[9px] ${index < step || step === 4 ? "bg-[#517848] text-white" : index === step ? "border border-[#72925b] bg-[#dcebcf] text-[#426338]" : "border border-[#dbe4d1] text-[#a5b197]"}`}
            >
              {index < step || step === 4 ? <Check size={11} /> : index + 1}
            </span>
            <span
              className={`hidden sm:block ${index <= step ? "text-[#5e7d4e]" : "text-[#a5b197]"}`}
            >
              {label}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
