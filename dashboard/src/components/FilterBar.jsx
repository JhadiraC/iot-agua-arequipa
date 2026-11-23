import { Pause, Play, RefreshCw } from "lucide-react";
import { POLL_INTERVALS, WATERSHEDS } from "../constants/thresholds";

export function FilterBar({
  selectedWatershed,
  onWatershedChange,
  selectedStation,
  onStationChange,
  stations,
  pollMs,
  onPollMsChange,
  autoRefresh,
  onToggleAutoRefresh,
  onManualRefresh,
  loading,
}) {
  return (
    <section className="flex flex-wrap items-end justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/80 p-4">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label
            htmlFor="watershed-select"
            className="mb-1 block text-xs font-medium text-slate-400"
          >
            Cuenca Hidrográfica
          </label>
          <select
            id="watershed-select"
            value={selectedWatershed}
            onChange={(e) => onWatershedChange(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
          >
            {WATERSHEDS.map((w) => (
              <option key={w} value={w}>
                {w}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="station-select"
            className="mb-1 block text-xs font-medium text-slate-400"
          >
            Estación (Nodo ESP32)
          </label>
          <select
            id="station-select"
            value={selectedStation}
            onChange={(e) => onStationChange(e.target.value)}
            className="min-w-[190px] rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
          >
            <option value="">Todas las estaciones ({stations.length})</option>
            {stations.map((s) => (
              <option key={s.document_id} value={s.station_id}>
                {s.station_id} — {s.watershed} {s.is_alert ? "⚠" : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div>
          <label
            htmlFor="poll-select"
            className="mb-1 block text-xs font-medium text-slate-400"
          >
            Polling (cuota Firestore)
          </label>
          <select
            id="poll-select"
            value={pollMs}
            onChange={(e) => onPollMsChange(Number(e.target.value))}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
          >
            {POLL_INTERVALS.map((opt) => (
              <option key={opt.ms} value={opt.ms}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={onToggleAutoRefresh}
          disabled={pollMs === 0}
          className={`mt-5 inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition ${
            autoRefresh && pollMs > 0
              ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25"
              : "border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700"
          } disabled:cursor-not-allowed disabled:opacity-50`}
        >
          {autoRefresh && pollMs > 0 ? (
            <>
              <Pause className="h-4 w-4" /> Auto ON
            </>
          ) : (
            <>
              <Play className="h-4 w-4" /> Auto OFF
            </>
          )}
        </button>

        <button
          type="button"
          onClick={onManualRefresh}
          disabled={loading}
          className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-sky-500 disabled:opacity-60"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Actualizar
        </button>
      </div>
    </section>
  );
}
