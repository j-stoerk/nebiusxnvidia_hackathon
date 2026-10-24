import { useState } from "react";
import type { FormEvent } from "react";
import { ArrowRight, Bot, Send, Sparkles } from "lucide-react";
import type { ChatMessage, Workspace } from "../types";
import { PanelTitle } from "./Dashboard";

export function ChatPanel({
  workspace,
  messages,
  busy,
  onSend,
}: {
  workspace: Workspace;
  messages: ChatMessage[];
  busy: boolean;
  onSend: (message: string, allow: boolean) => void;
}) {
  const [draft, setDraft] = useState(""),
    [allow, setAllow] = useState(false);
  function submit(e: FormEvent) {
    e.preventDefault();
    if (draft.trim() && !busy) {
      onSend(draft.trim(), allow);
      setDraft("");
    }
  }
  return (
    <section className="panel chat-panel">
      <PanelTitle
        eyebrow="NVIDIA NEMOTRON VIA NEBIUS"
        title="Charging assistant"
        right={
          <span className={`target-pill ${workspace.agent.configured ? "" : "neutral"}`}>
            <span className="status-dot" />
            {workspace.agent.configured ? "Configured" : "Not connected"}
          </span>
        }
      />
      <div className="chat-transcript" aria-live="polite">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <span className="ai-orb">
              <Sparkles size={25} />
            </span>
            <h3>A clearer view of your charging plan.</h3>
            <p>Ask about priorities, shortfalls, or the impact of a simulated change.</p>
            {[
              "Which vehicles are at risk of missing their targets?",
              "Explain the current cost and peak-power comparison.",
              "Why is EV-001 scheduled in these intervals?",
            ].map((prompt) => (
              <button
                key={prompt}
                onClick={() => setDraft(prompt)}
                disabled={!workspace.agent.configured || busy}
              >
                {prompt}
                <ArrowRight size={14} />
              </button>
            ))}
          </div>
        )}
        {messages.map((message, i) => (
          <article key={i} className={`chat-message ${message.role}`}>
            <span className="message-author">
              {message.role === "user"
                ? "YOU"
                : message.reply?.mode === "nemotron"
                  ? "NEMOTRON"
                  : "CONNECTION STATUS"}
            </span>
            <p>{message.text}</p>
            {message.reply?.tool_calls.map((call, index) => (
              <details className="tool-trace" key={index}>
                <summary>
                  {call.name} ·{" "}
                  {call.result && typeof call.result === "object" && "error" in call.result
                    ? "error"
                    : "result"}
                </summary>
                <pre>{JSON.stringify(call.result, null, 2)}</pre>
              </details>
            ))}
          </article>
        ))}
      </div>
      {!workspace.agent.configured && (
        <div className="connection-notice">
          <Bot size={18} />
          <span>
            Nemotron is not connected. Configure its server credentials to enable chat. Scheduling
            and simulation are available now.
          </span>
        </div>
      )}
      <form className="chat-compose" onSubmit={submit}>
        <textarea
          aria-label="Message Nemotron"
          placeholder="Ask about your charging operations…"
          rows={2}
          value={draft}
          disabled={!workspace.agent.configured || busy}
          onChange={(e) => setDraft(e.target.value)}
        />
        <div className="compose-footer">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={allow}
              onChange={(e) => setAllow(e.target.checked)}
              disabled={!workspace.agent.configured || busy}
            />
            Allow simulation changes
          </label>
          <button
            className="send-button"
            type="submit"
            aria-label="Send message"
            disabled={!workspace.agent.configured || busy || !draft.trim()}
          >
            <Send size={17} />
          </button>
        </div>
      </form>
    </section>
  );
}
