import { useCallback, useEffect, useState } from "react";
import { Droplets, Server } from "lucide-react";
import {
  API_BASE_URL,
  fetchHealth,
  fetchStations,
  fetchSummary,
  fetchTelemetry,
} from "./api/client";
import { AlertsTable } from "./components/AlertsTable";
import { FilterBar } from "./components/FilterBar";
import { KpiCards } from "./components/KpiCards";
import { StationsOverview } from "./components/StationsOverview";
import { TelemetryCharts } from "./components/TelemetryCharts";

export default function App() {
  const [selectedWatershed, setSelectedWatershed] = useState("Todas");
  const [selectedStation, setSelectedStation] = useState("");
  const [pollMs, setPollMs] = useState(10000);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const [health, setHealth] = useState(null);
  const [summary, setSummary] = useState(null);
  const [stations, setStations] = useState([]);
  const [telemetry, setTelemetry] = useState([]);
  const [alerts, setAlerts] = useState([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const watershedParam =
        selectedWatershed === "Todas" ? undefined : selectedWatershed;
      const stationParam = selectedStation || undefined;

      const [healthRes, summaryRes, stationsRes, telemetryRes, alertsRes] =
        await Promise.all([
          fetchHealth(),
          fetchSummary(),
          fetchStations(watershedParam),
          fetchTelemetry({
            watershed: watershedParam,
            station_id: stationParam,
            limit: 150,
          }),
          fetchTelemetry({
            watershed: watershedParam,
            station_id: stationParam,
            only_alerts: true,
            limit: 50,
          }),
        ]);

      setHealth(healthRes);
      setSummary(summaryRes);
      setStations(stationsRes);
      setTelemetry(telemetryRes);
      setAlerts(alertsRes);
      setLastUpdated(new Date());
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo conectar con la API del backend."
      );
    } finally {
      setLoading(false);
    }
  }, [selectedWatershed, selectedStation]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!autoRefresh || pollMs <= 0) return undefined;
    const timer = setInterval(loadData, pollMs);
    return () => clearInterval(timer);
  }, [autoRefresh, pollMs, loadData]);

  const handleWatershedChange = (watershed) => {
    setSelectedWatershed(watershed);
    setSelectedStation("");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-sky-500/15 p-2.5 text-sky-400 ring-1 ring-sky-500/30">
              <Droplets className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-slate-50 sm:text-xl">
                Monitoreo IoT de Calidad del Agua — Arequipa
              </h1>
              <p className="text-xs text-slate-400">
                Telemetría ESP32 · Cloud Run + Firestore · 5 Cuencas Hidrográficas
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-medium ${
                health?.status === "ok"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                  : "border-rose-500/40 bg-rose-500/10 text-rose-300"
              }`}
            >
              <Server className="h-3.5 w-3.5" />
              {health?.status === "ok"
                ? `API Online (${health.storage_mode})`
                : "API Desconectada"}
            </span>
            {lastUpdated && (
              <span className="hidden text-slate-400 sm:inline">
                Última actualización: {lastUpdated.toLocaleTimeString("es-PE")}
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6">
        {error && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            <strong>Error de conexión con {API_BASE_URL}:</strong> {error}
          </div>
        )}

        <FilterBar
          selectedWatershed={selectedWatershed}
          onWatershedChange={handleWatershedChange}
          selectedStation={selectedStation}
          onStationChange={setSelectedStation}
          stations={stations}
          pollMs={pollMs}
          onPollMsChange={setPollMs}
          autoRefresh={autoRefresh}
          onToggleAutoRefresh={() => setAutoRefresh((v) => !v)}
          onManualRefresh={loadData}
          loading={loading}
        />

        <KpiCards
          summary={summary}
          stations={stations}
          selectedWatershed={selectedWatershed}
        />

        <TelemetryCharts telemetry={telemetry} />

        <AlertsTable alerts={alerts} />

        <StationsOverview
          stations={stations}
          selectedStation={selectedStation}
          onSelectStation={setSelectedStation}
        />
      </main>
    </div>
  );
}
