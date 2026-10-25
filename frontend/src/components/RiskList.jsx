import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatDuration, kwh, timeLabel } from "@/utils/formatters";

export default function RiskList({ atRisk = [] }) {
  if (!atRisk.length) {
    return (
      <div className="rounded-md border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm text-muted-foreground">
        All scheduled vehicles meet their energy targets on the active plan.
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {atRisk.map((v) => {
        const dwell =
          v.arrival_time && v.departure_time
            ? formatDuration(new Date(v.departure_time) - new Date(v.arrival_time))
            : null;
        return (
          <li
            key={v.vehicle_id}
            className="flex items-start gap-3 rounded-md border border-amber-500/20 bg-amber-500/5 p-3"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold text-sm">{v.vehicle_id}</p>
                <Badge variant="warning">shortfall {kwh(v.shortfall_kwh)}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Departs {timeLabel(v.departure_time)}
                {dwell ? ` · window ${dwell}` : ""}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
