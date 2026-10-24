import { useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function FileUpload({ onUpload, busy }) {
  const [sessions, setSessions] = useState(null);
  const [prices, setPrices] = useState(null);

  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (sessions) onUpload(sessions, prices);
      }}
    >
      <div className="grid gap-2">
        <Label htmlFor="sessions">Sessions CSV</Label>
        <Input
          id="sessions"
          type="file"
          accept=".csv,text/csv"
          disabled={busy}
          onChange={(e) => setSessions(e.target.files?.[0] || null)}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="prices">Prices CSV (optional)</Label>
        <Input
          id="prices"
          type="file"
          accept=".csv,text/csv"
          disabled={busy}
          onChange={(e) => setPrices(e.target.files?.[0] || null)}
        />
      </div>
      <Button type="submit" disabled={busy || !sessions}>
        <Upload className="h-4 w-4" />
        Upload & validate
      </Button>
      <p className="text-xs text-muted-foreground leading-relaxed">
        Required: vehicle_id, arrival_time, departure_time, energy_required_kwh,
        max_charging_power_kw. Times must include timezone (e.g. Z).
      </p>
    </form>
  );
}
