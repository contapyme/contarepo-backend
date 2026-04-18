# ContaREPO Backend

Microservicio de reportes contables para ContaPYME. Se conecta a la misma base de datos que el backend principal en modo solo lectura y expone reportes financieros en múltiples formatos (JSON, PDF, Excel).

## Tecnologías

- **Python 3.11** + **FastAPI**
- **SQLAlchemy 2.0** (async) + **asyncpg** + **PostgreSQL**
- **Pydantic v2** para validación y esquemas
- **python-jose** para validación de tokens JWT emitidos por ContaPYME

## Estructura

```
app/
├── config.py           # Variables de entorno (Settings)
├── main.py             # Punto de entrada FastAPI, CORS, routers
├── dependencies.py     # Validación JWT, empresa activa
├── core/               # Seguridad, decodificación de tokens
├── db/                 # Sesión async, Base declarativa (read-only)
├── models/             # Modelos SQLAlchemy (espejo de contapyme-backend)
├── schemas/            # Esquemas Pydantic de respuesta
├── routers/
│   └── reports.py      # Todos los endpoints de reportes
└── services/           # Generación de reportes (lógica contable)
```

## Endpoints

| Endpoint | Descripción |
|---|---|
| `GET /api/v1/reports/balance-sheet` | Balance General |
| `GET /api/v1/reports/income-statement` | Estado de Resultados (EERR) |
| `GET /api/v1/reports/trial-balance` | Balance de Comprobación |
| `GET /api/v1/reports/journal` | Libro Diario |
| `GET /api/v1/reports/ledger` | Libro Mayor |
| `GET /api/v1/reports/f710` | Formulario 710 (SUNAT) |

Los reportes aceptan parámetros `fiscal_period_id`, `from_date`, `to_date` y el header `X-Company-ID`. La mayoría soporta `?format=pdf` o `?format=xlsx`.

## Variables de entorno

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/contapyme
SECRET_KEY=...           # Misma clave que contapyme-backend para validar JWT
CORS_ORIGINS=["http://localhost:5174"]
```

> Este servicio no escribe en la base de datos. Comparte el mismo `DATABASE_URL` que `contapyme-backend`.

## Ejecución local

```bash
# Instalar dependencias
pip install -e .

# Levantar en puerto 8001
uvicorn app.main:app --reload --port 8001

# Documentación interactiva
# http://localhost:8001/docs
```

## Docker

```bash
docker build -t contarepo-backend .
docker run -p 8001:8001 --env-file .env contarepo-backend
```

## Estructura de base de datos

ContaREPO no crea ni migra tablas propias. Accede en modo **solo lectura** a las tablas administradas por `contapyme-backend`, compartiendo el mismo `DATABASE_URL`.

Las tablas que consulta son:

| Tabla | Uso |
|---|---|
| `companies` | Verificar empresa activa del usuario |
| `users` / `user_companies` | Autenticación y autorización |
| `accounts` | Plan de cuentas para agrupaciones del reporte |
| `fiscal_periods` | Filtrar por período contable |
| `journal_entries` | Obtener asientos del período |
| `journal_entry_lines` | Débitos y créditos por cuenta |
| `cost_centers` | Filtros opcionales por centro de costo |

### `period_balances` — Caché de saldos (lectura)

ContaREPO también lee esta tabla para acelerar la generación de reportes sin recalcular desde los asientos cuando el caché está vigente.

| Columna | Tipo | Descripción |
|---|---|---|
| `company_id` | UUID FK → companies | Empresa |
| `account_id` | UUID FK → accounts | Cuenta contable |
| `year` | INTEGER | Año |
| `month` | INTEGER | Mes (1-12) |
| `total_debit` | NUMERIC(15,2) | Total débitos del período |
| `total_credit` | NUMERIC(15,2) | Total créditos del período |
| `calculated_at` | TIMESTAMPTZ | Fecha del último cálculo |

> Ver la documentación de `contapyme-backend` para el detalle completo de todas las tablas.

## Health check

```
GET /health → {"status": "ok", "service": "ContaREPO"}
```
