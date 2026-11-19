# Backend Serverless — Monitoreo IoT de Calidad del Agua (Arequipa)

API REST construida con **FastAPI** y diseñada para ejecutarse en **Google Cloud Run** con persistencia en **Cloud Firestore** (modo producción) o **SQLite local** (modo desarrollo y pruebas sin consumo de cuotas cloud).

## Estructura

```text
backend/
├── app/
│   ├── __init__.py
│   ├── config.py        # Variables de entorno y umbrales referenciales de alerta
│   ├── schemas.py       # Modelos Pydantic v2 con validación física
│   ├── alerts.py        # Motor de reglas de alerta (pH, OD, Conductividad)
│   ├── repository.py    # Patrón Repository: SQLiteLocalRepository y FirestoreRepository
│   └── main.py          # Endpoints FastAPI, CORS y validación X-API-KEY
├── tests/
│   ├── conftest.py
│   ├── test_alerts.py
│   └── test_api.py
├── .dockerignore
├── .env.example
├── Dockerfile
├── pytest.ini
└── requirements.txt
```

## Endpoints

| Método | Ruta | Auth | Descripción |
| --- | --- | --- | --- |
| `GET` | `/health` | Pública | Estado del servicio y `storage_mode` activo |
| `POST` | `/api/v1/telemetry` | `X-API-KEY` | Ingesta una lectura IoT, evalúa alertas y actualiza `stations` |
| `GET` | `/api/v1/telemetry` | Pública | Lista lecturas recientes (`watershed`, `station_id`, `only_alerts`, `limit`) |
| `GET` | `/api/v1/stations` | Pública | Estado actual por estación (`watershed` opcional) |
| `GET` | `/api/v1/summary` | Pública | Resumen global y promedios por cuenca |

### Umbrales referenciales de alerta (`app/config.py`)

- **pH**: alerta si `< 6.5` o `> 8.5`
- **Oxígeno disuelto**: alerta si `< 4.0 mg/L`
- **Conductividad eléctrica**: alerta si `> 2500.0 µS/cm`

## Ejecución local (desde `backend/`)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env
$env:STORAGE_MODE = "local"
$env:IOT_API_KEY = "dev-local-key"
uvicorn app.main:app --reload --port 8080
```

Documentación interactiva disponible en `http://127.0.0.1:8080/docs`.

## Pruebas automatizadas (desde `backend/`)

```powershell
pytest
```

## Contenedor Docker (desde `backend/`)

```powershell
docker build -t arequipa-iot-backend .
docker run --rm -p 8080:8080 `
  -e STORAGE_MODE=local `
  -e IOT_API_KEY=dev-local-key `
  arequipa-iot-backend
```

## Notas para despliegue en Cloud Run + Firestore

- Configurar `STORAGE_MODE=firestore`, `IOT_API_KEY` (recomendado vía Secret Manager) y `ALLOWED_ORIGINS` con la URL del dashboard.
- En Firestore, las consultas filtradas de `GET /api/v1/telemetry` combinan filtros de igualdad (`watershed`, `station_id`, `is_alert`) con `ORDER BY ingested_at DESC`, por lo que Firestore solicitará crear índices compuestos la primera vez que se ejecuten.
