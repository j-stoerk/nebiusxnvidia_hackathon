import { useEffect, useState } from "react";
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
          <Badge variant="warning">
            {status?.reason || "Set HF_TOKEN (Hugging Face) or Nebius credentials for chat"}
          </Badge>
        )}
      </div>

      <div className="max-h-72 space-y-3 overflow-auto rounded-xl border border-border bg-muted/30 p-3">
        {log.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Powered by NVIDIA Nemotron on Hugging Face Inference Providers. Ask why a vehicle is
            scheduled, which vehicles miss deadlines, or how to cut cost. OR-Tools still owns
            scheduling; the agent uses approved tools only.
          </p>
        ) : null}
        {log.map((entry, i) => (
          <div
            key={i}
            className={`rounded-xl px-3 py-2 text-sm animate-in-up ${
              entry.role === "user"
                ? "ml-8 bg-primary text-primary-foreground"
                : "mr-8 bg-card border border-border"
            }`}
          >
            <p className="whitespace-pre-wrap">{entry.text}</p>
            {entry.tools?.length ? (
              <p className="mt-1 text-[11px] opacity-80">
                Tools: {entry.tools.map((t) => t.tool).join(", ")}
              </p>
            ) : null}
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
          disabled={busy || !status?.configured}
          placeholder="Why is EV-001 scheduled between 12:00:00 and 12:15:00 UTC?"
          onChange={(e) => setMessage(e.target.value)}
        />
        <Button type="submit" disabled={busy || !status?.configured}>
          <Send className="h-4 w-4" />
          Ask agent
        </Button>
      </form>
    </div>
  );
}
