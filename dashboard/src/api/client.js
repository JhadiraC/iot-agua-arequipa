const RAW_API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8080";
export const API_BASE_URL = RAW_API_URL.replace(/\/+$/, "");

async function requestJson(path, params = {}) {
  const url = new URL(`${API_BASE_URL}${path}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "" && value !== "Todas") {
      url.searchParams.set(key, String(value));
    }
  });

  const response = await fetch(url.toString(), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`HTTP ${response.status}: ${text || response.statusText}`);
  }
  return response.json();
}

export function fetchHealth() {
  return requestJson("/health");
}

export function fetchSummary() {
  return requestJson("/api/v1/summary");
}

export function fetchStations(watershed) {
  return requestJson("/api/v1/stations", { watershed });
}

export function fetchTelemetry({ watershed, station_id, only_alerts, limit = 150 } = {}) {
  return requestJson("/api/v1/telemetry", {
    watershed,
    station_id,
    only_alerts: only_alerts ? "true" : undefined,
    limit,
  });
}
