import { useId } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const utcInput = value => value?.slice(0, 19) || "";
export const utcTime = value => value ? new Date(value + "Z").toISOString() : "";

export function Field({ label, type = "text", onChange, ...props }) {
  const id = useId();
  return <div className="grid min-w-0 gap-1.5"><Label htmlFor={id}>{label}</Label><Input id={id} type={type} step={type === "number" ? "any" : undefined} {...props}
    onChange={e => onChange(type === "number" && e.target.value !== "" ? Number(e.target.value) : e.target.value)} /></div>;
}

export function SelectField({ label, children, onChange, ...props }) {
  const id = useId();
  return <div className="grid min-w-0 gap-1.5"><Label htmlFor={id}>{label}</Label><select id={id} className="h-10 min-w-0 rounded-md border border-border bg-card px-3 text-sm focus-visible:outline-2 focus-visible:outline-primary" {...props} onChange={e => onChange(e.target.value)}>{children}</select></div>;
}
