import { cn } from "@/lib/utils";

export default function MetricCard({ label, value, hint, className }) {
  return (
    <div className={cn("min-w-0", className)}>
        <p className="text-xs font-medium text-muted-foreground">
          {label}
        </p>
        <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums text-foreground">{value}</p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
