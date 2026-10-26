import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { api } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

export default function AgentChat({ onWorkspace, busy, setBusy }) {
  const [message, setMessage] = useState("");
  const [allowChanges, setAllowChanges] = useState(false);
  const [status, setStatus] = useState(null);
  const [log, setLog] = useState([]);
  const transcript = useRef(null);

  useEffect(() => {
    if (transcript.current) transcript.current.scrollTop = transcript.current.scrollHeight;
  }, [log]);

  useEffect(() => {
    api.agentStatus().then(setStatus).catch(() => {});
  }, []);

  async function send(e) {
    e.preventDefault();
    if (!message.trim()) return;
    const markBusy = typeof setBusy === "function" ? setBusy : () => {};
    markBusy(true);
    const userMsg = message.trim();
    setMessage("");
    setLog((prev) => [...prev, { role: "user", text: userMsg }]);
    try {
      const result = await api.chat(userMsg, allowChanges);
      setLog((prev) => [
        ...prev,
        {
          role: "assistant",
          text: result.reply?.message || "No reply",
          mode: result.reply?.mode,
          tools: result.reply?.tool_calls,
        },
      ]);
      if (result.workspace && typeof onWorkspace === "function") onWorkspace(result.workspace);
    } catch (err) {
      setLog((prev) => [...prev, { role: "assistant", text: err.message, mode: "error" }]);
    } finally {
      markBusy(false);
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {status?.configured ? (
          <Badge variant="success">
            Nemotron ·{" "}
            {status.provider === "huggingface"
              ? `Hugging Face${status.hf_provider ? ` / ${status.hf_provider}` : ""}`
              : status.provider || "cloud"}{" "}
            · {status.model}
          </Badge>
        ) : (
          <Badge variant="outline">
            Local computed summary · no AI model call
          </Badge>
        )}
      </div>

      <div ref={transcript} aria-live="polite" className="max-h-72 space-y-3 overflow-auto rounded-md border border-border bg-muted/30 p-3">
        {log.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Ask about departure readiness, site power or cost. {status?.configured
              ? "The connected model uses checked results and approved tools."
              : "No model is connected. Summaries report the current planner results without an AI call."}
          </p>
        ) : null}
        {log.map((entry, i) => (
          <div
            key={i}
            className={`rounded-md px-3 py-2 text-sm ${
              entry.role === "user"
                ? "ml-8 bg-primary text-primary-foreground"
                : "mr-8 bg-card border border-border"
            }`}
          >
            <p className="whitespace-pre-wrap">{entry.text.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
              part.startsWith("**") ? <strong key={j}>{part.slice(2, -2)}</strong> : part
            )}</p>
            {entry.tools?.length ? (
              <p className="mt-1 text-[11px] opacity-80">
                Tools: {entry.tools.map((t) => t.tool).join(", ")}
              </p>
            ) : null}
            {entry.tools?.filter(t => t.verified_facts).map((tool, j) => <div key={j} className="mt-3 border-t border-border pt-2 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Computed tool facts</p>
              <p className="mt-1">Chargers: {tool.verified_facts.charger_ids.join(", ") || "none"} · battery energy {tool.verified_facts.battery_energy_delivered_kwh} kWh · active charging {tool.verified_facts.active_charging_hours} h</p>
              <p>{tool.verified_facts.allocation_count} intervals · {tool.verified_facts.fixed_connections ? "Fixed plug assignment" : "Movable plug assignment"}</p>
            </div>)}
          </div>
        ))}
      </div>

      <form className="grid gap-3" onSubmit={send}>
        <div className="flex items-center gap-3">
          <Switch
            id="allow-changes"
            checked={allowChanges}
            disabled={busy}
            onCheckedChange={setAllowChanges}
          />
          <Label htmlFor="allow-changes" className="cursor-pointer">
            Allow simulation changes (re-optimize / events)
          </Label>
        </div>
        <Textarea
          rows={3}
          value={message}
          disabled={busy || !status?.available}
          placeholder={status?.configured ? "Ask about the checked charging plan" : "Summarize readiness, peak and cost from the current plan"}
          onChange={(e) => setMessage(e.target.value)}
        />
        <Button type="submit" disabled={busy || !status?.available}>
          <Send className="h-4 w-4" />
          {status?.configured ? "Ask Nemotron" : "Show plan summary"}
        </Button>
      </form>
    </div>
  );
}
