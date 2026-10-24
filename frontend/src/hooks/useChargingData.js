import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";

export function useChargingData() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

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
      try {
        const result = await fn();
        const next = result.workspace || result;
        if (next.analytics || next.station) setData(next);
        else await refresh();
        if (successMessage) setNotice(successMessage);
        return result;
      } catch (err) {
        setError(err.message);
        throw err;
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
  };
}
