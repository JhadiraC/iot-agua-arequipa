# Simulador de Nodos ESP32 (`simulator/`)

Simula los 15 nodos ESP32 (3 estaciones por cada una de las 5 cuencas de Arequipa) enviando lecturas reales desde `data/processed/arequipa_sample_15_stations.csv` hacia `POST /api/v1/telemetry`.

## Uso de `esp32_simulator.py`

No requiere dependencias externas (usa solo la biblioteca estándar de Python).

### Modo secuencial (local)
```powershell
python simulator/esp32_simulator.py `
  --url http://127.0.0.1:8080/api/v1/telemetry `
  --api-key dev-local-key `
  --mode sequential `
  --interval 0.05
```

### Modo concurrente (5 nodos ESP32 en paralelo)
```powershell
python simulator/esp32_simulator.py `
  --url http://127.0.0.1:8080/api/v1/telemetry `
  --api-key dev-local-key `
  --mode concurrent `
  --workers 5 `
  --interval 0.05
```

Al finalizar, exporta las métricas de latencia en `simulator/latency_results.csv` con las columnas:
`timestamp,station_id,status_code,latency_ms`.

## Uso de `wokwi_esp32_sketch.ino`

1. Abre [Wokwi](https://wokwi.com/) y crea un proyecto **ESP32 (Arduino)**.
2. Copia el contenido de `simulator/wokwi_esp32_sketch.ino`.
3. Reemplaza `API_ENDPOINT` con tu URL pública de Cloud Run y `IOT_API_KEY` con tu clave.
4. Ejecuta la simulación y revisa el Serial Monitor (`115200` baudios).
