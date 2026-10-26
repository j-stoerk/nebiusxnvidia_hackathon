import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";

export function useChargingData() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [progress, setProgress] = useState(null);

  // Reveal real completed steps briefly; never delay the server or invent percentages.
  const presentStep = useCallback(async event => {
    setProgress(previous => ({ status: "running", events: [...(previous?.events || []), event] }));
    await new Promise(resolve => setTimeout(resolve, event.status === "complete" ? 240 : 140));
  }, []);
  const calculate = useCallback(() => api.optimize(presentStep), [presentStep]);
  const simulate = useCallback(event => api.simulateEvent(event, true, presentStep), [presentStep]);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const state = await api.getState();
      setData(state);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const run = useCallback(
    async (fn, successMessage) => {
      setBusy(true);
      setError(null);
      setNotice(null);
      setProgress(null);
      try {
        const result = await fn();
        const next = result.workspace || result;
        if (next.analytics || next.station) setData(next);
        else await refresh();
        if (successMessage) setNotice(successMessage);
        setProgress(previous => previous && { ...previous, status: "complete" });
        return result;
      } catch (err) {
        try { setData(await api.getState()); } catch { /* Keep the prior view if the network is down. */ }
        setError(err.message);
        setProgress(previous => previous && { ...previous, status: "error" });
        return null;
      } finally {
        setBusy(false);
      }
    },
    [refresh]
  );

  return {
    data,
    busy,
    error,
    notice,
    setNotice,
    setError,
    setBusy,
    refresh,
    run,
    setData,
    calculate,
    simulate,
    progress,
  };
}
