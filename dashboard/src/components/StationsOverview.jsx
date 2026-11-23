import { MapPin } from "lucide-react";

export function StationsOverview({ stations, selectedStation, onSelectStation }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-sky-400" />
          <h2 className="text-base font-semibold text-slate-100">
            Estado Actual de Estaciones ({stations.length})
          </h2>
        </div>
        <span className="text-xs text-slate-400">
          Vista optimizada desde colección <code className="text-slate-300">stations</code>
        </span>
      </div>

      {stations.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-500">
          Aún no hay estaciones reportando telemetría. Ejecuta el simulador ESP32 para
          ingestar lecturas.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {stations.map((st) => {
            const isSelected = selectedStation === st.station_id;
            return (
              <button
                key={st.document_id}
                type="button"
                onClick={() =>
                  onSelectStation(isSelected ? "" : st.station_id)
                }
                className={`rounded-lg border p-3.5 text-left transition ${
                  isSelected
                    ? "border-sky-500 bg-sky-500/10"
                    : "border-slate-800 bg-slate-950/60 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <span className="font-mono text-sm font-semibold text-slate-100">
                      {st.station_id}
                    </span>
                    <span className="ml-2 text-xs text-sky-400">{st.watershed}</span>
                  </div>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                      st.is_alert
                        ? "bg-rose-500/20 text-rose-300"
                        : "bg-emerald-500/20 text-emerald-300"
                    }`}
                  >
                    {st.is_alert ? "Alerta" : "Normal"}
                  </span>
                </div>
                <p className="mt-1 truncate text-xs text-slate-400" title={st.location}>
                  {st.location || "Sin descripción"}
                </p>
                <div className="mt-2.5 grid grid-cols-4 gap-1 text-xs tabular-nums">
                  <div className="rounded bg-slate-900 px-1.5 py-1">
                    <span className="block text-[10px] text-slate-500">pH</span>
                    <span className="text-slate-200">{st.last_reading.ph.toFixed(2)}</span>
                  </div>
                  <div className="rounded bg-slate-900 px-1.5 py-1">
                    <span className="block text-[10px] text-slate-500">Temp</span>
                    <span className="text-slate-200">
                      {st.last_reading.water_temp_c.toFixed(1)}°C
                    </span>
                  </div>
                  <div className="rounded bg-slate-900 px-1.5 py-1">
                    <span className="block text-[10px] text-slate-500">OD</span>
                    <span className="text-slate-200">
                      {st.last_reading.dissolved_oxygen_mg_l.toFixed(1)}
                    </span>
                  </div>
                  <div className="rounded bg-slate-900 px-1.5 py-1">
                    <span className="block text-[10px] text-slate-500">CE</span>
                    <span className="text-slate-200">
                      {Math.round(st.last_reading.electrical_conductivity_us_cm)}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
