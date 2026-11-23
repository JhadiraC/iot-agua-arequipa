import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { THRESHOLDS } from "../constants/thresholds";

function formatAxisLabel(record, index) {
  if (record.sample_date) {
    return `${record.station_id} (${record.sample_date.slice(0, 7)})`;
  }
  return `#${index + 1}`;
}

function ChartCard({ title, unit, color, data, dataKey, referenceLines = [] }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
        <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
          {unit}
        </span>
      </div>

      {data.length === 0 ? (
        <div className="flex h-56 items-center justify-center text-sm text-slate-500">
          Sin lecturas para los filtros seleccionados
        </div>
      ) : (
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="label"
                tick={{ fill: "#94a3b8", fontSize: 10 }}
                interval="preserveStartEnd"
                minTickGap={28}
              />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} width={46} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                labelStyle={{ color: "#e2e8f0", fontWeight: 600 }}
                formatter={(value) => [`${Number(value).toFixed(2)} ${unit}`, title]}
              />
              {referenceLines.map((ref) => (
                <ReferenceLine
                  key={ref.label}
                  y={ref.y}
                  stroke={ref.color}
                  strokeDasharray="4 4"
                  label={{
                    value: ref.label,
                    position: "insideTopRight",
                    fill: ref.color,
                    fontSize: 10,
                  }}
                />
              ))}
              <Line
                type="monotone"
                dataKey={dataKey}
                stroke={color}
                strokeWidth={2}
                dot={{ r: 2.5 }}
                activeDot={{ r: 5 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export function TelemetryCharts({ telemetry }) {
  // Backend returns newest first; reverse for left-to-right chronological charts
  const chartData = [...telemetry]
    .reverse()
    .map((item, idx) => ({
      ...item,
      label: formatAxisLabel(item, idx),
    }));

  return (
    <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <ChartCard
        title="pH del Agua"
        unit="pH"
        color="#38bdf8"
        data={chartData}
        dataKey="ph"
        referenceLines={[
          { y: THRESHOLDS.phMin, color: "#f59e0b", label: `Mín ${THRESHOLDS.phMin}` },
          { y: THRESHOLDS.phMax, color: "#ef4444", label: `Máx ${THRESHOLDS.phMax}` },
        ]}
      />
      <ChartCard
        title="Temperatura del Agua"
        unit="°C"
        color="#fb923c"
        data={chartData}
        dataKey="water_temp_c"
      />
      <ChartCard
        title="Oxígeno Disuelto (OD)"
        unit="mg/L"
        color="#34d399"
        data={chartData}
        dataKey="dissolved_oxygen_mg_l"
        referenceLines={[
          { y: THRESHOLDS.doMin, color: "#ef4444", label: `Mín ${THRESHOLDS.doMin} mg/L` },
        ]}
      />
      <ChartCard
        title="Conductividad Eléctrica (CE)"
        unit="µS/cm"
        color="#a78bfa"
        data={chartData}
        dataKey="electrical_conductivity_us_cm"
        referenceLines={[
          {
            y: THRESHOLDS.ecMax,
            color: "#ef4444",
            label: `Máx ${THRESHOLDS.ecMax} µS/cm`,
          },
        ]}
      />
    </section>
  );
}
