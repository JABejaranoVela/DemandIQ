# Contrato inicial de datos

## Fuente y selección

El parser m5-sales-v1 conserva producto × tienda × día; esto no cierra la frecuencia del futuro
experimento predictivo. Tiendas y fechas inclusivas son obligatorias. Los filtros de artículos,
departamentos y categorías son explícitos y opcionales. No se seleccionan automáticamente las
mejores series, no se recorta historia ni se excluyen series de ceros.

Se requieren sales_train_evaluation.csv y calendar.csv. Precios no participa en esta fase.
CSV UTF-8 con cabecera única. Ventas requiere item_id, store_id, dept_id, cat_id, state_id y
los d_x necesarios. Otros campos se ignoran; id de competición no es la identidad de negocio.

IDs seleccionados: letras ASCII, dígitos y guion bajo, de 1 a 100 caracteres.
Calendar requiere d y date, identificadores d_N positivos, fechas ISO válidas, correspondencia
única y cobertura del rango. No se inventan fechas ni se rellenan huecos.
Una selección vacía o con filtros explícitos no encontrados falla.

La validación de valores y metadatos de ventas se aplica al subconjunto seleccionado.
No se afirma validar todos los valores fuera de él.

## Cero y errores

Cero es una observación válida. Vacío, NaN, texto, negativo, fracción y desbordamiento de entero
se rechazan; nunca se convierten en cero. Una fila SKU/tienda repetida en el origen se rechaza
aunque sus valores coincidan.

Un fallo revierte toda la transacción CORE del intento. No se borra el histórico ni se cargan
silenciosamente las filas restantes. RAW conserva el intento, originales y primer error.
Imputación, cuarentena parcial y reglas de corrección quedan pendientes.

## Identidad y procedencia

- Venta: clave primaria (item_id, store_id, date).
- Procesamiento: SHA-256 de hashes de archivos, nombres esperados, fuente, parser y selección
  canónica con listas ordenadas sin repetidos.
- Cada intento admitido por el escritor recibe su propio UUID.
- Reingesta idéntica: completed y reused_load_id al original, sin transformar ni insertar.
- Un archivo reordenado puede cambiar de hash. La clave de negocio evita duplicados igualmente.
- Solapamiento igual: conserva ventas y load_id originales, registra records_unchanged.
- Valor o metadatos distintos: correction_not_supported, sin sobrescritura.
- Cada intento conserva sus fuentes para auditar también las observaciones solapadas.

No se implementa una regla implícita de última escritura.

## Contadores

records_processed: observaciones diarias seleccionadas, validadas por el transformador y
entregadas a persistencia antes de completar o detenerse. No son filas anchas originales.

records_rejected: celdas/filas identificadas en el primer error cuando se conoce su cantidad.
Es 0 en fallos de archivo/esquema sin una cantidad determinable. No cuenta todos los errores
posibles: la validación se detiene en el primero.

records_inserted y records_unchanged: resultados confirmados; ambos quedan en 0 tras rollback.
Una reutilización por fingerprint tiene contadores 0: enlaza los originales mediante reused_load_id.

## Atomicidad y recuperación

Hay un escritor mediante advisory lock PostgreSQL. Otro proceso recibe ingestion_busy; no hay cola.
Con el bloqueo adquirido, running registra el intento antes de acceder a los archivos.
Las ventas y completed se confirman en la misma transacción.
La API de ventas consulta solo observaciones de cargas completadas; trazabilidad sí muestra fallos.

Un cierre brusco puede dejar running, pero PostgreSQL revierte las ventas pendientes.
La siguiente ingesta con el bloqueo marca esos intentos failed/interrupted.
Si PostgreSQL cae, puede ser imposible registrar el fallo inmediatamente; se recupera después.

Se parsea la copia archivada por checksum. Las copias existentes se verifican antes de reutilizar.
No se ejecuta limpieza automática del archivo. Conservar originales y base juntos permite auditoría.
La publicación de forecasts y snapshots analíticos pertenece a fases posteriores.

## Controles propios

tests/conftest.py genera seis ventas inventadas de dos productos y una tienda,
identificadas como synthetic-control en una base de pruebas dedicada.
La CLI solo ingiere M5 real; estos controles no forman parte del recorrido de usuario.
Sirven para probar el formato y recorrido sin redistribuir M5; no son datos Walmart,
escenarios de inventario ni datos para evaluar forecasting.
