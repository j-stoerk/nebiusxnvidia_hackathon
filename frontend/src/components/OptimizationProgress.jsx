import { Check, LoaderCircle } from "lucide-react";
import { eur, kwh, kw } from "@/utils/formatters";

const LABELS = { inputs: "Input checks", FCFS: "First come, first served", EDF: "Earliest deadline first", LLF: "Least laxity first", energy: "Departure energy targets", peak: "Minimum peak power", cost: "Energy and demand cost", validation: "Independent constraint checks" };

export default function OptimizationProgress({ progress }) {
  if (!progress) return null;
  const finished = progress.status === "complete";
  const stages = [...new Set(progress.events.map(event => event.stage))];
  const current = progress.events.at(-1)?.stage;
  const references = progress.events.filter(event => event.metrics);
  return <section className="mb-5 rounded-lg border border-border bg-card px-5 py-4" aria-label="Calculation progress" aria-live="polite">
    <div className="flex items-center gap-2 text-sm font-medium">
      {finished ? <Check className="h-4 w-4 text-success" /> : progress.status === "running" ? <LoaderCircle className="h-4 w-4 animate-spin text-primary" /> : null}
      {finished ? "Checked charging plan ready" : progress.status === "error" ? "Calculation stopped — review the message above" : "Building your charging comparison"}
    </div>
    {!finished && <>
      <ol className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground">{stages.map(stage => <li key={stage} className="flex items-center gap-1.5">
        {stage !== current || progress.events.at(-1)?.status === "complete" ? <Check className="h-3 w-3 text-success" /> : <span className="h-2 w-2 rounded-full bg-primary" />}{LABELS[stage] || stage}
      </li>)}</ol>
      {references.length > 0 && <div className="mt-3 flex flex-wrap gap-4 border-t border-border pt-3 text-xs">{references.map(({ stage, metrics }) => <span key={stage}><strong>{stage}</strong> · {kw(metrics.peak_power_kw)} · {eur(metrics.cost_eur)} · {kwh(metrics.unserved_kwh)} unserved</span>)}</div>}
      <p className="mt-3 text-xs text-muted-foreground">Baseline results appear first. The previous plan stays visible until the new plan passes its checks.</p>
    </>}
  </section>;
}
