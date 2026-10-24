import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

export default function StationSettings({ station, onSave, busy }) {
  const [form, setForm] = useState(null);

  useEffect(() => {
    if (station) {
      setForm({
        station_id: station.station_id,
        station_power_limit_kw: station.station_power_limit_kw,
        charger_count: station.charger_count || station.chargers?.length || 10,
        charger_max_power_kw: station.charger_max_power_kw || 11,
        slot_minutes: station.slot_minutes || 15,
        charging_efficiency: station.charging_efficiency ?? 1,
        fixed_connections: station.fixed_connections ?? true,
        demand_tariff: {
          eur_per_kw: station.demand_tariff?.eur_per_kw ?? 15.2,
          prior_peak_kw: station.demand_tariff?.prior_peak_kw ?? 0,
          period: station.demand_tariff?.period || "month",
          timezone: station.demand_tariff?.timezone || "Europe/Berlin",
        },
        simulated: true,
      });
    }
  }, [station]);

  if (!form) return null;

  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const { chargers: _c, ...payload } = form;
        onSave(payload);
      }}
    >
      <div className="grid gap-2">
        <Label>Station power limit (kW)</Label>
        <Input
          type="number"
          min="1"
          step="1"
          value={form.station_power_limit_kw}
          disabled={busy}
          onChange={(e) => setForm({ ...form, station_power_limit_kw: Number(e.target.value) })}
        />
      </div>
      <div className="grid gap-2">
        <Label>Number of chargers</Label>
        <Input
          type="number"
          min="1"
          max="50"
          value={form.charger_count}
          disabled={busy}
          onChange={(e) => setForm({ ...form, charger_count: Number(e.target.value) })}
        />
      </div>
      <div className="grid gap-2">
        <Label>Charger max power (kW)</Label>
        <Input
          type="number"
          min="1"
          step="0.1"
          value={form.charger_max_power_kw}
          disabled={busy}
          onChange={(e) => setForm({ ...form, charger_max_power_kw: Number(e.target.value) })}
        />
      </div>
      <div className="grid gap-2">
        <Label>Charging efficiency (0–1)</Label>
        <Input
          type="number"
          min="0.5"
          max="1"
          step="0.01"
          value={form.charging_efficiency}
          disabled={busy}
          onChange={(e) => setForm({ ...form, charging_efficiency: Number(e.target.value) })}
        />
      </div>
      <div className="grid gap-2">
        <Label>Demand tariff (€/kW above prior peak)</Label>
        <Input
          type="number"
          min="0"
          step="0.1"
          value={form.demand_tariff.eur_per_kw}
          disabled={busy}
          onChange={(e) =>
            setForm({
              ...form,
              demand_tariff: { ...form.demand_tariff, eur_per_kw: Number(e.target.value) },
            })
          }
        />
      </div>
      <div className="grid gap-2">
        <Label>Prior billing peak (kW)</Label>
        <Input
          type="number"
          min="0"
          step="0.1"
          value={form.demand_tariff.prior_peak_kw}
          disabled={busy}
          onChange={(e) =>
            setForm({
              ...form,
              demand_tariff: { ...form.demand_tariff, prior_peak_kw: Number(e.target.value) },
            })
          }
        />
      </div>
      <div className="flex items-center gap-3">
        <Switch
          checked={form.fixed_connections}
          disabled={busy}
          onCheckedChange={(v) => setForm({ ...form, fixed_connections: v })}
        />
        <Label>Fixed plug per vehicle (no charger switching)</Label>
      </div>
      <div className="grid gap-2">
        <Label>Slot duration</Label>
        <Input value={`${form.slot_minutes} min`} disabled readOnly />
      </div>
      <Button type="submit" variant="secondary" disabled={busy}>
        Save station settings
      </Button>
      <p className="text-xs text-muted-foreground">
        Simulated depot settings — demand charge is incremental above the prior billing peak.
      </p>
    </form>
  );
}
