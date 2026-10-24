import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export default function MetricCard({ label, value, hint, className, style }) {
  return (
    <Card className={cn("overflow-hidden", className)} style={style}>
      <CardContent className="p-4">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <p className="mt-1.5 text-xl font-semibold tracking-tight text-foreground">{value}</p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}
