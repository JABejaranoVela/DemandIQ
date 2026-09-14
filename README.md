# DemandIQ

Sistema de análisis y forecasting de ventas observadas y, en fases posteriores, apoyo a
decisiones de reposición. Portfolio de Python backend, Data Engineering y BI.

**Estado: FOUNDATION + DATA FOUNDATION validadas con M5 real.** Están implementadas la ingesta
batch, la persistencia PostgreSQL, la trazabilidad y una API de consulta.
[Forecasting V1](docs/forecasting-spec.md) está implementado conforme al protocolo 1.0:
backtesting, selección previa al test, persistencia y reporte reproducible.
[Guía de ejecución](docs/forecasting-runbook.md).

## Problema y límites

El recorrido final será datos → transformación → forecast → escenario de inventario →
recomendación explicable → API/BI. DemandIQ no es un ERP, un gestor de compras ni un SaaS multiempresa.

El dataset principal es [Walmart M5 Forecasting Accuracy](https://www.kaggle.com/competitions/m5-forecasting-accuracy).
**Ventas observadas ≠ demanda real no restringida.** M5 no ofrece stock histórico, lead times,
proveedores ni stockouts identificados. Los escenarios futuros se identificarán como
configurados/simulados cuando corresponda. No se afirma recuperar demanda perdida.

## IMPLEMENTED

- Selección explícita por tiendas, artículos, departamentos, categorías y fechas inclusivas.
- Originales archivados por SHA-256; versión de parser y configuración reproducible.
- Cargas running/completed/failed con identificación, fechas, errores y contadores.
- Transformación ancha a ventas producto/tienda/día, conservando ceros y rechazando ausencias.
- Alembic, claves de negocio, inserciones por lotes y transacción atómica.
- Reingestas idénticas y selecciones solapadas sin duplicar ni sobrescribir ventas.
- API versionada, OpenAPI y liveness/readiness separados.
- Tests unitarios, API, integración PostgreSQL y E2E con controles sintéticos propios.
- Docker Compose y workflow de GitHub Actions.
- Forecasting V1: seis folds, baseline semanal, candidato global Poisson recursivo y test final.
- Runs, predicciones y métricas persistidos; modelos con checksum e informes regenerables.

## PLANNED

- Política de correcciones del origen.
- Forecast operativo posterior al test y exposición definitiva de resultados de forecasting.
- Inventario configurado, reposición explicable y publicación de resultados analíticos.
- Power BI y definición de vigencia de resultados.
- Revisión de condiciones para compartir datos e informes.
- GHCR de producción, VPS, backups y Nginx.

## Stack y arquitectura actual

Python 3.13, FastAPI, Pydantic/pydantic-settings, PostgreSQL 18, SQLAlchemy 2, Psycopg 3,
Alembic, pandas, NumPy, scikit-learn, uv, pytest/HTTPX, Ruff, Docker Compose y GitHub Actions.

Las versiones estables concretas están en uv.lock. NumPy se utiliza en forecasting.
threadpoolctl, dependencia de scikit-learn, limita la ejecución a dos hilos CPU.
Schemathesis se pospone; tienen prioridad los tests de datos, reglas y contratos HTTP explícitos.

Un paquete Python, con API de lectura y CLI batch. La API no ejecuta ingestas ni entrenamientos.
Las migraciones son explícitas, no se ejecutan automáticamente al arrancar el servidor.

- **RAW:** raw.ingestion_loads registra intentos y referencias a copias originales por checksum.
  Los bytes se conservan en un archivo local/volumen. Base y archivo deben conservarse juntos.
- **CORE:** productos, tiendas y ventas normalizadas.
- **ANALYTICS:** runs, forecasts evaluados y métricas del protocolo 1.0 (migración 0002).

Detalles: [contrato de datos](docs/data-contract.md) y [decisiones](docs/decisions.md).

## Configuración y ejecución local

Requisitos: Python 3.13, uv y Docker con contenedores Linux.

Copia .env.example a .env y establece DEMANDIQ_POSTGRES_PASSWORD con una contraseña local
propia. .env está ignorado por Git y excluido de la imagen.

```text
uv sync --locked
docker compose up -d postgres --wait
uv run --locked alembic upgrade head
uv run --locked uvicorn demandiq.api.app:create_app --factory --reload
```

La plantilla usa PostgreSQL en **127.0.0.1:55432** y la API en **127.0.0.1:8000**.
Las variables DEMANDIQ_* tienen prioridad sobre .env.
DEMANDIQ_DATABASE_URL admite una conexión PostgreSQL como secreto opcional y tiene prioridad
sobre los campos separados; no se incluyen URLs con credenciales.
Compose utiliza los campos separados, host postgres y puerto interno 5432.

PostgreSQL crea la base; Alembic crea el esquema. No se usa create_all.
Cambiar credenciales o nombre de base en .env no reconfigura un volumen ya inicializado.

## Ejecución completa en Docker

```text
docker compose up -d postgres --wait
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose up -d api --wait
```

La imagen usa un usuario sin privilegios y dependencias bloqueadas sin herramientas de desarrollo.
No incorpora secretos ni datasets. Ambos servicios se publican solo en loopback.
El batch utiliza la misma imagen mediante docker compose run --rm api demandiq.

El healthcheck PostgreSQL comprueba disponibilidad. El de API comprueba conexión y migración.
Sin migraciones, /health puede responder, pero /api/v1/ready devuelve 503.

## Preparar e ingerir M5

No se descarga automáticamente. Obtén los datos por tus propios medios autorizados y revisa
las [condiciones de la competición](https://www.kaggle.com/competitions/m5-forecasting-accuracy/rules).
La autorización para publicar datos/derivados sigue pendiente. Las pruebas no requieren Kaggle.

Coloca en data/raw/:

- sales_train_evaluation.csv: obligatorio.
- calendar.csv: obligatorio, relaciona d_x con fechas reales.
- sell_prices.csv: previsto para la fase de precios; **no se exige ni procesa en este hito**.

Configura DEMANDIQ_M5_STORE_IDS como lista JSON y DEMANDIQ_M5_START_DATE/END_DATE como fechas ISO.
Los filtros opcionales ITEM_IDS, DEPARTMENT_IDS y CATEGORY_IDS también son listas JSON.
Una lista vacía no restringe ese atributo; los filtros se combinan mediante intersección.
Tiendas y fechas son obligatorias: no existe una selección M5 predeterminada.

```text
uv run --locked demandiq ingest
```

O con los mismos filtros configurados en .env:

```text
docker compose run --rm api demandiq ingest
```

La CLI admite --store-id, --item-id, --department-id y --category-id repetibles;
--start-date, --end-date, --data-dir, --archive-dir.
Los argumentos explícitos sustituyen al filtro correspondiente del entorno.

Se archivan los originales completos una vez por contenido para auditoría. La transformación
lee bloques y solo las columnas temporales elegidas; expande únicamente las series seleccionadas.
Necesitas espacio para originales y copias archivadas.
Para reprocesar una copia, localízala mediante sus checksums y restaura los nombres originales
en otro directorio de entrada. Las referencias están registradas por carga.

## Endpoints

| Método y ruta | Uso |
|---|---|
| GET /health | Liveness sin consultar la base. |
| GET /api/v1/health | Alias versionado. |
| GET /api/v1/ready | PostgreSQL accesible y esquema esperado. |
| GET /api/v1/loads | Intentos, paginados mediante limit/offset. |
| GET /api/v1/loads/{load_id} | Fuente, selección, checksums, estado y contadores. |
| GET /api/v1/sales | Ventas de item_id/store_id entre start_date y end_date. |
| GET /docs | Swagger UI. |
| GET /openapi.json | Contrato OpenAPI. |

La consulta de ventas utiliza los item_id, store_id y fechas de la carga M5 seleccionada.

Cada venta incluye load_id de su primera inserción. Un solapamiento idéntico no cambia su procedencia.
El rango es inclusivo; los resultados se ordenan por fecha. Hay 500 filas por defecto y máximo
2000 por página. Si next_after_date no es null, úsalo como after_date para continuar.
Sin observaciones se devuelve una lista vacía, nunca ceros inventados.

Errores: error.code, error.message y error.details.
422 para parámetros inválidos; 404 para carga inexistente; 503 para base/esquema no disponible.
La API no expone rutas del archivo ni credenciales.

Readiness no implica actualidad analítica. Las cargas distinguen fecha de procesamiento y rango
histórico. La publicación definitiva de forecasts y su API pertenecen a otra fase;
los informes actuales solo aceptan runs completed.

## Tests y calidad

Sin PostgreSQL:

```text
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -m "not integration"
```

Para todos los tests, crea una base dedicada y desechable cuyo nombre termine en _test.
Las pruebas limpian exclusivamente las tablas DemandIQ de esa base y aplican migraciones reales.
Se niegan a usar una base con otro sufijo.

```text
docker compose exec postgres createdb -U demandiq demandiq_test
```

Créala una sola vez. Si has cambiado el usuario PostgreSQL, utiliza ese usuario.

PowerShell:

```powershell
$env:DEMANDIQ_POSTGRES_DB = "demandiq_test"
$env:DEMANDIQ_RUN_DB_TESTS = "1"
uv run --locked pytest
Remove-Item Env:DEMANDIQ_POSTGRES_DB
Remove-Item Env:DEMANDIQ_RUN_DB_TESTS
```

Bash:

```bash
DEMANDIQ_POSTGRES_DB=demandiq_test DEMANDIQ_RUN_DB_TESTS=1 uv run --locked pytest
```

Si usas DEMANDIQ_DATABASE_URL, sustitúyela también por la de pruebas: tiene prioridad.
Sin DEMANDIQ_RUN_DB_TESTS=1 los tests de PostgreSQL se marcan skipped; CI los activa.
Los controles sintéticos existen exclusivamente en tests/conftest.py y se generan en directorios
temporales. La CLI de la aplicación ingiere M5 real; ya no ofrece control-data ni --source.

## Validación de esta entrega

- 57 tests pasan con PostgreSQL real: 43 unitarios/API y 14 integración/E2E.
- Ruff lint y format --check pasan.
- Alembic upgrade, downgrade/upgrade de prueba y check sin diferencias pasan.
- Docker build y arranque de ambos servicios con healthchecks pasan.
- El E2E automatizado comprueba persistencia, reingesta y consulta API con controles aislados.
- Hay dos avisos de deprecación de dependencias del TestClient; no causan fallos.

Los archivos originales M5 están disponibles localmente en data/raw/ y se han comprobado
sus metadatos: 30.490 series, 3.049 productos y ventas del 2011-01-29 al 2016-05-22.
La primera carga real se ha validado con CA_1 / FOODS_1, del 2015-01-01 al 2016-05-22:
216 productos, 508 días y 109.728 observaciones. CSV y PostgreSQL coinciden en todas las
observaciones: 169.836 unidades y 55.701 ceros. Reingesta sin duplicados y consultas HTTP
contrastadas para tres SKUs. La selección está en el .env local y sigue siendo configurable;
fue provisional para DATA FOUNDATION y ahora está aceptada para Forecasting V1.
Los seis controles previos permanecen identificados
como synthetic-control/DEMO_STORE y se excluyeron de las comprobaciones M5.

Primera ingesta: 91,3 s de proceso y 133,5 MiB de pico RSS Python; reingesta: 0,7 s.
No se necesitaron cambios de implementación ni optimizaciones. Las evidencias locales
están en artifacts/m5-validation-report.md y artifacts/m5-reconciliation.json, ignoradas
por Git. Esta validación corresponde al subconjunto indicado, no a todo el dataset.

## Validación de Forecasting V1 con M5 real

Run completed: 6f2358fb-f814-4c2e-accf-e59c7a710d66. Protocolo 1.0, 216 SKU,
seis folds y test final de 14 días. Tiempo: 13.521 s;
pico RSS del proceso Python: 265.52 MiB.

La política congelada seleccionó weekday_mean_4. El candidato redujo el RMSE
global de desarrollo, pero ganó solo 3 de 6 folds y empeoró el Bias absoluto.
No se modificaron parámetros ni selección tras consultar el test.

Se reconciliaron independientemente 42.336 predicciones y 10.736 métricas contra
PostgreSQL, además de los checksums de siete modelos. La reingesta M5 sigue siendo
idempotente y la API existente responde correctamente.

Evidencias locales, ignoradas por Git:
artifacts/6f2358fb-f814-4c2e-accf-e59c7a710d66/forecasting-v1-report.md,
results.json, forecasts.csv y validation.json. El informe puede regenerarse desde
PostgreSQL sin entrenar; Windows y Linux pueden utilizar distintos saltos de línea,
pero su contenido normalizado coincide. Consulta la [guía](docs/forecasting-runbook.md).

## CI y entrega

.github/workflows/ci.yml instala mediante uv.lock, ejecuta Ruff, pytest con PostgreSQL 18,
Alembic check y Docker build. Las credenciales CI son efímeras.
No publica imágenes ni despliega producción.

El workflow está configurado, pero su ejecución remota requiere alojar el repositorio en GitHub.
No se configura un remoto ni se hace push. Las comprobaciones locales no equivalen a un run
remoto de Actions. Git está inicializado; esta entrega no crea commits.

## Próximas decisiones

Forecasting V1 está implementado según el [protocolo 1.0](docs/forecasting-spec.md),
incluida la política de selección baseline/candidato y su test separado.
Después: política del escenario de inventario, integración con reposición y KPIs.

Las dos revisiones Markdown originales permanecen en la raíz como contexto histórico.
Este README describe el comportamiento implementado.
