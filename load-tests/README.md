# Pruebas de Carga con Locust (`load-tests/`)

Script `locustfile.py` que carga las **1,306 lecturas reales** de `data/processed/arequipa_iot_clean.csv` y simula sensores ESP32 concurrentes contra el backend FastAPI.

## Instalación

```powershell
# Desde la raíz del proyecto (usando el venv del backend o un venv dedicado)
backend\.venv\Scripts\pip.exe install -r load-tests/requirements.txt
```

## Presupuesto de cuota gratuita de Cloud Firestore

La capa gratuita de Firestore otorga **20,000 escrituras/día** y **50,000 lecturas/día**.
Cada petición `POST /api/v1/telemetry` realiza **2 escrituras** (`telemetry` + upsert en `stations`).

Con `wait_time` de `2–5 s` (~0.28 req/s por sensor) y 80% de tareas de escritura:

| Escenario | Sensores (`-u`) | Ramp-up (`-r`) | Duración (`-t`) | Escrituras Firestore aprox. |
| --- | ---: | ---: | ---: | ---: |
| 1. Carga baja | 5 | 5/s | 1 min | ~170 |
| 2. Carga media | 50 | 10/s | 1 min | ~1,700 |
| 3. Pico / Autoescalado | 200 | 25/s | 1 min | ~6,800 |
| **Total 3 escenarios** | — | — | **3 min** | **~8,670 (< 45% de cuota diaria)** |

> **Recomendación**: prueba primero contra el backend en modo `STORAGE_MODE=local` para validar tus comandos sin gastar cuota cloud, y luego ejecuta los 3 escenarios acotados contra tu URL de Cloud Run.

## Comandos de ejecución (desde la raíz del proyecto)

```powershell
$env:IOT_API_KEY = "tu-clave-configurada"
$TARGET_URL = "http://127.0.0.1:8080"   # o https://tu-servicio.run.app

# Escenario 1: 5 sensores concurrentes (1 minuto)
backend\.venv\Scripts\locust.exe -f load-tests/locustfile.py --headless `
  -u 5 -r 5 -t 1m --host $TARGET_URL --csv load-tests/results_5_users

# Escenario 2: 50 sensores concurrentes (1 minuto)
backend\.venv\Scripts\locust.exe -f load-tests/locustfile.py --headless `
  -u 50 -r 10 -t 1m --host $TARGET_URL --csv load-tests/results_50_users

# Escenario 3: 200 sensores concurrentes (1 minuto)
backend\.venv\Scripts\locust.exe -f load-tests/locustfile.py --headless `
  -u 200 -r 25 -t 1m --host $TARGET_URL --csv load-tests/results_200_users
```

Cada escenario genera `*_stats.csv`, `*_stats_history.csv` y `*_failures.csv` con latencias `p50`, `p95`, `p99`, `RPS` y tasa de error para documentar en el informe final.
