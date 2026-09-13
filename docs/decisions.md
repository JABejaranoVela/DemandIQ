# Decisiones técnicas breves

## 001 — Monolito modular

Aceptada. Un paquete Python compartido por API y batch. Configuración, ingesta, persistencia y
consulta tienen responsabilidades concretas. Sin microservicios: no hay equipos ni escalado
independiente que justifiquen su coste. Sin interfaces genéricas ni carpetas preventivas.

## 002 — PostgreSQL y Alembic

Aceptada. Un único motor en aplicación y pruebas de integración. Claves, transacciones y
restricciones sostienen idempotencia y consistencia. Alembic evoluciona el esquema explícitamente;
no se usa create_all. PostgreSQL 18 es la versión estable de Compose/CI.
La imagen 18 persiste bajo /var/lib/postgresql. Migrar y servir son operaciones distintas.

## 003 — M5 y ventas observadas

Aceptada. Historia retail por producto y tienda, con selección configurable. No se interpreta
cero como stockout ni se afirma recuperar demanda no observada. La normalización conserva el
grano de origen; el experimento predictivo aún no está definido.

## 004 — No redistribuir M5

Aceptada. Originales y derivados locales están ignorados y excluidos de la imagen.
Las condiciones de publicación se verificarán también para informes Power BI.
CI y demo utilizan controles sintéticos propios etiquetados.
Los derechos de datos son distintos de la futura licencia del código.

## 005 — RAW archivado y CORE normalizado

Aceptada. RAW registra selección, intento y checksum; un archivo local por contenido conserva
los bytes. CORE contiene productos, tiendas y ventas. No hay tablas duplicadas sin propósito
ni ANALYTICS vacío. Archivo y base deben conservarse juntos.
sell_prices.csv se documenta, pero se procesará cuando exista un uso de precios.

## 006 — Idempotencia y correcciones

Aceptada para esta fase. Fingerprint detecta reingestas exactas; clave compuesta protege contra
solapamientos. Cada repetición conserva un intento enlazado al original. Valores iguales no
duplican; correcciones distintas se rechazan hasta acordar su política.
Un escritor y transacción por carga evitan carreras y resultados parciales.
No se borra todo antes de ingerir.

## 007 — Dependencias y entrega

Aceptada. Python 3.13 y uv.lock, versiones estables sin RC/beta. NumPy es transitivo de pandas.
No se instala scikit-learn antes de implementar forecasting. Schemathesis se pospone frente a
las pruebas explícitas de datos, persistencia y API. Docker/CI ahora; despliegue, GHCR de
producción y Nginx después.

## 008 — Protocolo Forecasting V1

Aceptada el 2026-09-14. El protocolo 1.0 queda definido en
[Forecasting V1](forecasting-spec.md): CA_1 / FOODS_1, 508 días, horizonte de 14 días,
seis folds expansivos y test final. Se comparan un baseline semanal suavizado y un
HistGradientBoostingRegressor global con Poisson y predicción recursiva. RMSE acumulado
es la métrica principal; la selección se fija con desarrollo antes del test.
La aprobación cierra las decisiones metodológicas del primer experimento. Forecasting
permanece sin implementar; no se añaden precios, reposición ni Power BI en esta tarea.
