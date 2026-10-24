import Dashboard from "./pages/Dashboard.jsx";
import { useChargingData } from "./hooks/useChargingData.js";
import { useTheme } from "./hooks/useTheme.js";

export default function App() {
  const state = useChargingData();
  const theme = useTheme();
  return <Dashboard state={state} theme={theme} />;
}
