export const money = (value: number) =>
  new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" }).format(value);
export const number = (value: number, digits = 1) =>
  value.toLocaleString("en-GB", { maximumFractionDigits: digits });
export const costDifference = (delta: number, percent: number | null) =>
  `${money(Math.abs(delta))} ${delta >= 0 ? "less" : "more"} than FCFS${percent === null ? "" : ` · ${number(Math.abs(percent))}%`}`;
export const time = (value: string) =>
  new Date(value).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
export const date = (value: string) =>
  new Date(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
export const localInput = (value: string) => new Date(value).toISOString().slice(0, 16);
export const isoInput = (value: string) => new Date(value + ":00Z").toISOString();
