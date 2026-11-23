import { Activity, AlertTriangle, Percent, Radio } from "lucide-react";

export function KpiCards({ summary, stations, selectedWatershed }) {
  const activeStationAlerts = stations.filter((s) => s.is_alert).length;

  let totalReadings = summary?.total_readings ?? 0;
  let totalAlerts = summary?.total_alerts ?? 0;
  let alertPct = summary?.alert_percentage ?? 0;
  let totalStations = summary?.total_stations ?? stations.length;

  if (selectedWatershed && selectedWatershed !== "Todas" && summary?.by_watershed) {
    const w = summary.by_watershed.find((item) => item.watershed === selectedWatershed);
    totalReadings = w?.total_readings ?? 0;
    totalAlerts = w?.total_alerts ?? 0;
    alertPct = w?.alert_percentage ?? 0;
    totalStations = stations.length;
  }

  const cards = [
    {
      title: "Total de Lecturas",
      value: totalReadings.toLocaleString("es-PE"),
      subtitle:
        selectedWatershed === "Todas"
          ? "5 cuencas de Arequipa"
          : `Cuenca ${selectedWatershed}`,
      icon: Activity,
      accent: "text-sky-400 bg-sky-500/10 border-sky-500/30",
    },
    {
      title: "Estaciones Monitoreadas",
      value: totalStations.toLocaleString("es-PE"),
      subtitle: `${activeStationAlerts} con alerta en última lectura`,
      icon: Radio,
      accent: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
    },
    {
      title: "Alertas Registradas",
      value: totalAlerts.toLocaleString("es-PE"),
      subtitle: "Fuera de umbral referencial",
      icon: AlertTriangle,
      accent:
        totalAlerts > 0
          ? "text-amber-400 bg-amber-500/10 border-amber-500/30"
          : "text-slate-400 bg-slate-800 border-slate-700",
    },
    {
      title: "% de Alertas",
      value: `${Number(alertPct).toFixed(1)}%`,
      subtitle: "Proporción sobre lecturas",
      icon: Percent,
      accent:
        alertPct >= 25
          ? "text-rose-400 bg-rose-500/10 border-rose-500/30"
          : "text-indigo-400 bg-indigo-500/10 border-indigo-500/30",
    },
  ];

  return (
    <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.title}
            className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 shadow-sm"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
                  {card.title}
                </p>
                <p className="mt-2 text-3xl font-bold text-slate-50">{card.value}</p>
                <p className="mt-1 text-xs text-slate-400">{card.subtitle}</p>
              </div>
              <div className={`rounded-lg border p-2.5 ${card.accent}`}>
                <Icon className="h-5 w-5" />
              </div>
            </div>
          </div>
        );
      })}
    </section>
  );
}
