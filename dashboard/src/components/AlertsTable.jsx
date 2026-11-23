import { AlertTriangle } from "lucide-react";

export function AlertsTable({ alerts }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          <h2 className="text-base font-semibold text-slate-100">
            Alertas Recientes ({alerts.length})
          </h2>
        </div>
        <span className="text-xs text-slate-400">
          Umbrales: pH [6.5–8.5] · OD ≥ 4.0 mg/L · CE ≤ 2500 µS/cm
        </span>
      </div>

      {alerts.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">
          No se registran alertas para el filtro actual.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-800 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-3 py-2.5">Cuenca</th>
                <th className="px-3 py-2.5">Estación</th>
                <th className="px-3 py-2.5">Parámetro(s) Fuera de Rango</th>
                <th className="px-3 py-2.5">pH</th>
                <th className="px-3 py-2.5">Temp (°C)</th>
                <th className="px-3 py-2.5">OD (mg/L)</th>
                <th className="px-3 py-2.5">CE (µS/cm)</th>
                <th className="px-3 py-2.5">Fecha Muestra</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {alerts.slice(0, 25).map((row) => (
                <tr key={row.id} className="hover:bg-slate-800/40">
                  <td className="px-3 py-2.5 font-medium text-sky-300">
                    {row.watershed}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-xs text-slate-200">
                    {row.station_id}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-wrap gap-1.5">
                      {row.alert_reasons.map((reason) => (
                        <span
                          key={reason}
                          className="inline-flex rounded-full border border-rose-500/40 bg-rose-500/15 px-2.5 py-0.5 text-xs font-medium text-rose-300"
                        >
                          {reason}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-slate-200">
                    {row.ph.toFixed(2)}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-slate-200">
                    {row.water_temp_c.toFixed(1)}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-slate-200">
                    {row.dissolved_oxygen_mg_l.toFixed(2)}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-slate-200">
                    {row.electrical_conductivity_us_cm.toFixed(1)}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-xs text-slate-400">
                    {row.sample_date}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
