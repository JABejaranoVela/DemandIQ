# Ejecutar y reproducir Forecasting V1

La metodología está congelada en [forecasting-spec.md](forecasting-spec.md), protocolo 1.0.
La implementación ejecuta seis folds, selección global y test final. No genera todavía
un forecast operativo posterior al test ni implementa reposición o Power BI.

## Preparación y ejecución local

Requiere la ingesta real validada de CA_1 / FOODS_1, 2015-01-01 a 2016-05-22, en PostgreSQL.
Los controles synthetic-control / DEMO_STORE quedan excluidos por la consulta de origen.

```text
uv sync --locked
uv run --locked alembic upgrade head
uv run --locked demandiq forecast backtest
```

La CLI devuelve run_id y la ruta del informe. El comando ejecuta el protocolo versionado;
los filtros M5 del .env son para ingesta y no modifican este experimento. No hay opciones de
tuning ni cambios de horizonte. Los tests inyectan solo una selección sintética de tres SKU
con las mismas fechas, features, configuración, folds y horizonte.

DEMANDIQ_FORECAST_ARTIFACTS_DIR configura únicamente la ubicación de resultados
(por defecto artifacts/forecasting). También puede utilizarse --artifacts-dir.

## Docker

```text
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose up -d api --wait
docker compose run --rm -T api demandiq forecast backtest
```

API y batch comparten imagen. Los modelos e informes se conservan en el volumen
forecasting_artifacts, montado en /app/artifacts/forecasting. No se añade un servicio batch.

Para copiar los resultados al workspace, sustituye RUN_ID por el identificador mostrado.
El directorio local artifacts debe existir:

```text
docker compose cp api:/app/artifacts/forecasting/RUN_ID artifacts/
```

## Resultados

Cada ejecución tiene un directorio propio:

- forecasting-v1-report.md: protocolo, métricas por fold, selección, test, segmentos y tiempos.
- results.json: run y todas las métricas, incluidas las de cada SKU, denominadores,
  configuración efectiva, versiones, cargas fuente y checksums.
- forecasts.csv: todas las predicciones y objetivos observados de evaluación, con sus segmentos.
- fold_1-candidate.pkl … fold_6-candidate.pkl y test-candidate.pkl: modelos por corte.

El informe y los exports se construyen desde PostgreSQL. Se pueden regenerar sin entrenar:

```text
uv run --locked demandiq forecast report --run-id RUN_ID
docker compose run --rm -T api demandiq forecast report --run-id RUN_ID
```

Cada backtest crea un run diferente: no reutiliza resultados ni elige configuraciones según
la puntuación anterior. La reproducción numérica requiere los mismos datos y versiones.
Se conserva semilla 42, dos hilos CPU mediante threadpoolctl y configuración completa.
threadpoolctl es una dependencia de scikit-learn, declarada explícitamente al utilizarla.
No se promete identidad binaria entre plataformas o versiones distintas.

Los pickle son artefactos locales generados, no una entrada pública. Antes de cargarlos
deben verificarse procedencia, checksum y versiones; no se deserializan archivos externos
en la CLI. Los paths registrados corresponden al entorno que entrenó (host o contenedor).

## Persistencia y fallos

La migración 0002 añade solo tres tablas en analytics:

- forecast_runs: selección, huellas, configuración, tiempos, etapas, decisión, artefactos y estado.
- forecasts: predicción y objetivo observado por run/etapa/método/SKU/tienda/fecha.
- forecast_metrics: métricas por run/etapa/método/ámbito, con numerador, denominador y estado.

Las etapas y sus resultados se guardan transaccionalmente. La decisión se confirma en
PostgreSQL antes de entrenar/evaluar el test y no cambia con su resultado.

Un run running o failed no es un resultado válido para servir. Los informes solo aceptan
un run completed explícito; no existe una publicación automática del último intento.
Si se necesita resolver el último resultado válido, se filtra completed antes de ordenar
por finished_at. No se ha implementado la API final de forecasting.

Un advisory lock permite un escritor de forecasting. Tras una interrupción, la siguiente
ejecución con el bloqueo marca running abandonados como failed/interrupted.
Los resultados anteriores completed y sus artefactos se conservan. Un fallo al exportar
el informe no invalida cálculos completed: se puede repetir forecast report.
Archivo y PostgreSQL deben conservarse juntos. No hay limpieza automática de artefactos.

Falta de historia completa produce insufficient_history y un run fallido, con los SKU
afectados cuando se conocen; no se omiten productos para mejorar métricas.
Veintiocho días bastan como contexto de inferencia, pero un entrenamiento a un paso
necesita al menos un objetivo posterior. Un entrenamiento global con suma de objetivos
cero registra candidate_not_trainable; no cambia de modelo ni inventa valores.

## Interpretación

- RMSE14 se calcula sobre errores acumulados por SKU/corte. El global agrupa errores
  cuadrados; no promedia RMSE de folds ni cancela errores entre productos.
- WAPE usa errores absolutos diarios y Bias el signo predicho menos observado.
- Los porcentajes con denominador cero son null/undefined, sin epsilon.
- Los terciles de volumen y de proporción de ceros se ajustan con entrenamiento;
  los empates se ordenan por item_id para reproducibilidad. No excluyen SKU.
- La regla exige menor RMSE global, al menos cuatro victorias de seis y Bias absoluto
  no peor. Empates conservan baseline. La comparación en test no cambia la selección.
- Los tiempos por etapa incluyen preparación, ajuste, inferencia y métricas, sin la
  persistencia de esa etapa. El total del run incluye persistencia, pero no exportar el informe.
- En Linux se registra el pico RSS de vida del proceso Python; no incluye PostgreSQL
  ni Docker Desktop. En Windows aparece null. Es una medida de ejecución, no un límite.

## Pruebas

Se conservan los tests de Data Foundation. La suite completa requiere una base *_test;
nunca se utilizan los datos M5 reales en CI.

```powershell
$env:DEMANDIQ_POSTGRES_DB = "demandiq_test"
$env:DEMANDIQ_RUN_DB_TESTS = "1"
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
Remove-Item Env:DEMANDIQ_POSTGRES_DB
Remove-Item Env:DEMANDIQ_RUN_DB_TESTS
```

Si DEMANDIQ_DATABASE_URL está definida, también debe apuntar a la base de pruebas.
