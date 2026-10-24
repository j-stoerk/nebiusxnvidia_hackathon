/** Keep API transactions here so views only describe what the operator sees. */
import { useEffect, useReducer } from "react";
import { api, createWorkspace, updateWorkspace, guideStep } from "./api";
import type { ChatMessage, Reply, Station, Workspace } from "./types";

export type Tab = "overview" | "schedule" | "vehicles" | "agent";
export type Dialog = "upload" | "station" | "event" | null;
type State = {
  data: Workspace | null;
  busy: string | null;
  error: string;
  notice: string;
  tab: Tab;
  modal: Dialog;
  messages: ChatMessage[];
  step: number | null;
};
const initial = (): State => ({
  data: null,
  busy: "Loading workspace",
  error: "",
  notice: "",
  tab: "overview",
  modal: null,
  messages: [],
  step: new URLSearchParams(location.search).get("demo") === "1" ? 0 : null,
});
const remember = (data: Workspace) => {
  sessionStorage.setItem("chargewise-workspace", data.workspace_id);
  return data;
};
const errorText = (error: unknown) => (error instanceof Error ? error.message : "Request failed");

function initialWorkspace() {
  const cached =
    new URLSearchParams(location.search).get("demo") === "1"
      ? null
      : sessionStorage.getItem("chargewise-workspace");
  return cached
    ? api<Workspace>(`/workspaces/${cached}`).catch(() => createWorkspace())
    : createWorkspace();
}

export function useWorkspace() {
  const [state, set] = useReducer(
    (current: State, patch: Partial<State>) => ({ ...current, ...patch }),
    undefined,
    initial,
  );
  const accept = (data: Workspace) => {
    set({ data: remember(data), error: data.last_error || "" });
    return data;
  };

  useEffect(() => {
    let mounted = true;
    initialWorkspace()
      .then((data) => {
        if (mounted) accept(data);
      })
      .catch((error) => {
        if (mounted) set({ error: errorText(error) });
      })
      .finally(() => {
        if (mounted) set({ busy: null });
      });
    return () => {
      mounted = false;
    };
  }, []);

  async function run(operation: () => Promise<Workspace>, label: string, keepGuide = false) {
    set({
      busy: label,
      error: "",
      notice: "",
      ...(!keepGuide && { step: null }),
    });
    try {
      return accept(await operation());
    } catch (error) {
      set({ error: errorText(error) });
      // Refresh after a conflict without hiding the failed operation's message.
      if (state.data) {
        try {
          set({
            data: await api<Workspace>(`/workspaces/${state.data.workspace_id}`),
          });
        } catch {
          /* Keep the last visible state. */
        }
      }
    } finally {
      set({ busy: null });
    }
  }

  const mutate = (endpoint: string, fields = {}, method = "POST") =>
    run(
      () => updateWorkspace(state.data!, endpoint, fields, method),
      "Calculating validated schedules",
    );

  async function load(stress: boolean | "capacity" = false, guided = false) {
    const next = await run(
      () =>
        createWorkspace(
          guided || stress === "capacity" ? "capacity" : stress ? "stress" : "normal",
        ),
      "Loading scenario",
    );
    if (next)
      set({
        step: guided ? 0 : null,
        messages: [],
        tab: "overview",
        notice: guided ? "" : "Scenario loaded. Run the optimizer to compare schedules.",
      });
  }

  async function nextStep() {
    if (!state.data || state.step === null) return;
    if (state.step === 4) {
      set({ step: null, tab: "schedule" });
      return;
    }
    const result = await run(() => guideStep(state.data!, state.step!), "Running demo step", true);
    if (result && !result.stale)
      set({
        step: state.step + 1,
        notice: state.step === 3 ? "Duplicate event ignored. State remains unchanged." : "",
      });
  }

  async function chat(message: string, allow_changes: boolean) {
    if (!state.data) return;
    const messages: ChatMessage[] = [...state.messages, { role: "user", text: message }];
    set({
      messages,
      busy: "Nemotron is working",
      error: "",
      ...(allow_changes && { step: null }),
    });
    try {
      const response = await api<{ reply: Reply; workspace: Workspace }>(
        `/workspaces/${state.data.workspace_id}/chat`,
        {
          expected_version: state.data.state_version,
          message,
          allow_changes,
        },
      );
      accept(response.workspace);
      set({
        messages: [
          ...messages,
          {
            role: "assistant",
            text: response.reply.message,
            reply: response.reply,
          },
        ],
      });
    } catch (error) {
      set({ error: errorText(error) });
    } finally {
      set({ busy: null });
    }
  }

  async function upload(form: FormData) {
    form.set("expected_version", String(state.data!.state_version));
    const next = await run(
      () => api<Workspace>(`/workspaces/${state.data!.workspace_id}/upload`, form),
      "Validating CSV",
    );
    if (next && !next.stale)
      set({
        modal: null,
        messages: [],
        notice: "CSV validated. Both schedules are ready.",
      });
  }

  async function configure(station: Station) {
    const next = await mutate("station", { station }, "PUT");
    if (next && !next.stale) set({ modal: null });
  }

  async function simulate(event: object) {
    const next = await mutate("events", { event });
    if (next)
      set({
        modal: null,
        notice: next.stale ? "" : "Event handled. The validated plan is ready.",
      });
  }

  const advance = () =>
    mutate("advance", {
      time: new Date(
        Math.min(Date.parse(state.data!.now) + 3600000, Date.parse(state.data!.horizon_end)),
      ).toISOString(),
    });
  return {
    ...state,
    set,
    load,
    mutate,
    nextStep,
    chat,
    upload,
    configure,
    simulate,
    advance,
  };
}

export type Controller = ReturnType<typeof useWorkspace>;
