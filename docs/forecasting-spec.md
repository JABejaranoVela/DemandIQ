# DemandIQ — Forecasting V1

Status: Accepted  
Protocol version: 1.0  
Accepted on: 2026-09-14  
Implementation status: Not implemented

## 1. Objetivo y alcance

Estimar ventas observadas diarias por SKU y tienda durante los 14 días posteriores a un
corte, comparar un baseline con un único candidato mediante backtesting temporal y
conservar forecasts, métricas y procedencia reproducibles. El método seleccionado
alimentará posteriormente el módulo de reposición.

M5 contiene ventas observadas, no demanda no restringida. El protocolo no recupera
ventas perdidas ni identifica stockouts. Inventario, reposición, Power BI y nuevas
fuentes operativas quedan fuera de esta fase.

Este documento es la referencia aceptada para implementar el protocolo 1.0. El
[estudio previo](forecasting-v1-specification.md) conserva el análisis y la propuesta
anteriores a la aprobación; sus decisiones pendientes quedan resueltas aquí.

## 2. Datos y evidencia estadística

### Selección aceptada

| Parámetro | Valor |
|---|---|
| Fuente | Walmart M5; source = m5 |
| Tienda | CA_1 |
| Departamento | FOODS_1 |
| Periodo observado, inclusivo | 2015-01-01 → 2016-05-22 |
| Grano | SKU × tienda × día |
| SKU | 216 |
| Días por SKU | 508 |
| Observaciones | 109.728 |

Los parámetros siguen siendo configurables: estos valores definen el experimento 1.0,
no reglas de negocio universales. Los registros synthetic-control / DEMO_STORE quedan
excluidos. Se utilizan sales_train_evaluation.csv y el mapeo d_x → fecha de calendar.csv.
sell_prices.csv no participa.

DATA FOUNDATION está validada: 169.836 unidades, 55.701 ceros, sin duplicados, nulos ni
rechazos, con reconciliación completa origen/PostgreSQL e ingesta idempotente.

### Distribución e intermitencia

Las estadísticas siguientes describen los 508 días completos; no deben reutilizarse
como features o segmentos de un corte anterior.

| Indicador | Valor |
|---|---:|
| Media de unidades por SKU/día | 1,548 |
| Mediana | 0 |
| Desviación estándar | 2,933 |
| Percentiles 95 / 99 | 7 / 14 unidades |
| Máximo diario de un SKU | 92 unidades |
| Mediana de las medias diarias por SKU | 0,929 |
| Rango de medias diarias por SKU | 0,031–10,451 |
| Observaciones con cero | 50,76 % |
| Mediana del porcentaje de ceros por SKU | 51,87 % |
| Días positivos por SKU | 11–505 |
| SKU sin ninguna venta en el periodo | 0 |
| SKU con al menos 50 % / 75 % / 90 % / 95 % de ceros | 114 / 27 / 6 / 1 |
| SKU con alguna racha de al menos 28 / 90 / 180 ceros | 109 / 50 / 16 |
| Mayor racha de ceros | 379 días, FOODS_1_102 |

FOODS_1_099 acumula 5.309 unidades; FOODS_1_079, solo 16 unidades en 11 días positivos.
Los diez productos con más ventas concentran el 25,1 % del volumen.

Los terciles de volumen contienen 72 SKU cada uno, ordenados por ventas acumuladas.
Son grupos relativos para diagnóstico, no clasificaciones empresariales ni filtros:

| Tercil | Media diaria por SKU | Participación en unidades | Porcentaje de ceros |
|---|---:|---:|---:|
| Superior | 1,309–10,451 | 69,59 % | 27,93 % |
| Intermedio | 0,715–1,291 | 20,90 % | 51,77 % |
| Inferior | 0,031–0,711 | 9,51 % | 72,59 % |

En evaluación, los segmentos de volumen e intermitencia se recalculan exclusivamente
con el entrenamiento disponible en cada corte. Los umbrales de ceros son descriptivos,
no motivos automáticos de exclusión.

### Estructura temporal y extremos

El diagnóstico separado del entrenamiento inicial (2015-01-01 → 2016-02-14) muestra:

- Ventas agregadas medias de unas 289 unidades los martes y 425 los sábados.
- Mayor venta media de fin de semana en 167 SKU y autocorrelación semanal agregada de 0,51.
- Descenso agregado aproximado del 12,5 % entre los primeros y últimos 56 días.
- Cambios locales: FOODS_1_004 pasa de 10,4 a 21,8 unidades diarias entre dos ventanas
  consecutivas de 28 días.
- 94 observaciones inusuales en 56 SKU según una regla exploratoria: venta de al menos
  10 unidades y superior a la media más seis desviaciones de los 28 días anteriores.
  Esta regla describe candidatos a revisión; no elimina ni modifica observaciones.

Mayo de 2015 promedia 399 unidades diarias y noviembre 231. Una diferencia mensual
no demuestra estacionalidad anual. El máximo de 92 unidades de FOODS_1_218
(2015-02-14) se conserva. Los ceros simultáneos de 2015-12-25 coinciden con Christmas,
pero no prueban por sí solos un cierre de tienda.

El detalle generado se conserva localmente en artifacts/forecasting-data-profile.json,
ignorado por Git. Es evidencia derivada de consultas de ventas y estadísticas por SKU,
no configuración del experimento ni requisito para leer esta especificación.
La reproducción debe utilizar la misma selección, rangos de diagnóstico y datos
identificados por la trazabilidad de ingesta, excluyendo siempre la fuente sintética.

## 3. Histórico y horizonte

Se mantienen los 508 días. El primer entrenamiento tiene 410 días, aproximadamente
58 semanas: suficientes para estudiar patrones semanales sin introducir una hipótesis
de estacionalidad anual. Más historia puede incorporar regímenes antiguos; dos SKU
no tienen ventas positivas durante 2014.

| Alternativa considerada | Días por SKU | Observaciones |
|---|---:|---:|
| Periodo aceptado | 508 | 109.728 |
| Desde 2014-01-01 | 873 | 188.568 |
| Histórico completo disponible | 1.941 | 419.256 |

La ampliación es técnicamente manejable, pero no necesaria para este experimento.
No se amplía ni recorta el histórico en función del resultado del test.

El horizonte principal es de 14 días, con una predicción diaria por SKU: dos ciclos
semanales y un compromiso entre utilidad e incertidumbre. Siete días podrían resultar
cortos para reposición; 28 añaden dificultad sin una necesidad operativa acordada.

Lead time y review period siguen fuera de este protocolo. Si su suma futura supera
14 días, el forecast no cubre el periodo de protección: deberá revisarse el horizonte,
sin extrapolaciones implícitas.

## 4. Protocolo temporal y restricciones sobre leakage

Ventana expansiva desde 2015-01-01, seis folds de desarrollo y un test final.
Todos los intervalos son inclusivos y todos los SKU comparten cortes.

| Etapa | Último día observado | Periodo pronosticado |
|---|---|---|
| Fold 1 | 2016-02-14 | 2016-02-15 → 2016-02-28 |
| Fold 2 | 2016-02-28 | 2016-02-29 → 2016-03-13 |
| Fold 3 | 2016-03-13 | 2016-03-14 → 2016-03-27 |
| Fold 4 | 2016-03-27 | 2016-03-28 → 2016-04-10 |
| Fold 5 | 2016-04-10 | 2016-04-11 → 2016-04-24 |
| Fold 6 | 2016-04-24 | 2016-04-25 → 2016-05-08 |
| Test final | 2016-05-08 | 2016-05-09 → 2016-05-22 |

Reglas obligatorias:

1. El corte representa el cierre del día, con ventas completas disponibles hasta esa fecha.
2. El candidato se reajusta en cada fold. Sus objetivos de entrenamiento no superan el corte.
3. Los 14 pasos se generan desde un único origen, sin incorporar ventas reales intermedias.
4. Las ventanas evaluadas no se solapan. En el siguiente fold pueden usarse observaciones
   anteriores que ya serían conocidas.
5. Codificaciones, segmentos y transformaciones ajustables utilizan solo entrenamiento.
6. Los lags y ventanas se calculan por SKU/tienda, excluyendo el objetivo y sin mezclar series.
7. No se usan splits aleatorios, validación interna aleatoria ni estadísticas del futuro.
8. El test no se utiliza para ajustar hiperparámetros, features, horizonte o política de selección.

El test está reservado para comparación de modelos desde la definición del protocolo.
Ya hubo auditoría y análisis descriptivo de todo el histórico: no se presenta como
un conjunto nunca examinado.

Tras evaluar el test, el método seleccionado puede reajustarse con los 508 días y
producir el forecast 2016-05-23 → 2016-06-05. Es una ejecución distinta del test y no
dispone de observaciones objetivo en el CSV actual.

## 5. Baseline

Un único baseline: media de las cuatro últimas observaciones del mismo día de la semana
disponibles en el corte. Los ceros participan en la media.

Para cada día futuro se toman las cuatro fechas históricas más recientes con su mismo
día de semana. El patrón de siete valores se repite durante las dos semanas; el
baseline no se actualiza con ventas futuras ni con sus propias predicciones.

Requiere 28 días completos. Aprovecha el patrón semanal y suaviza un cero o pico aislado.
El último valor es demasiado sensible al ruido; una media reciente sin día de semana
omite el patrón observado; el naïve semanal puro depende de una sola observación.

## 6. Candidato global y estrategia recursiva

Un único HistGradientBoostingRegressor de scikit-learn, compartido por los 216 productos,
con pérdida Poisson. Aprende relaciones no lineales entre actividad reciente, calendario
y producto, compartiendo información entre series.

La pérdida admite objetivos cero y utiliza un enlace logarítmico para estimaciones
medias positivas. No se afirma que las ventas sigan una distribución Poisson ni que
el modelo resuelva stockouts o intermitencia por sí solo. Las 216 categorías de producto
caben dentro del límite de 255 categorías por variable.

| Parámetro | Configuración inicial |
|---|---|
| loss | poisson |
| max_iter | 100 |
| learning_rate | 0.1 |
| max_leaf_nodes | 15 |
| min_samples_leaf | 50 |
| random_state | Semilla fija, registrada en la configuración de ejecución |
| early_stopping | false |

No se realiza búsqueda de hiperparámetros. La configuración efectiva y versiones se
persisten para reproducción. Estos valores son iniciales y conservadores, no optimizados.

El entrenamiento es a un paso. En inferencia, el modelo genera sucesivamente los 14 días.
Si un lag o rolling necesita un valor posterior al corte, utiliza exclusivamente la
predicción ya generada para ese SKU y fecha. Esta aproximación recursiva puede propagar
errores y debe evaluarse como tal, sin sustituirla por 14 predicciones con históricos
reales actualizados.

No se entrenan modelos individuales por SKU ni se incorporan frameworks adicionales.
Los modelos lineales exigirían más interacciones manuales; Random Forest puede aumentar
el tamaño sin ventaja demostrada. La explicación se apoya en variables, ejemplos y
errores por segmento, sin atribuciones causales.

## 7. Features y disponibilidad temporal

Exactamente siete variables. Los lags se definen respecto al día objetivo t.

| Feature | Definición | Disponibilidad y utilidad |
|---|---|---|
| lag_1 | Venta en t−1 | Histórico o predicción previa; actividad inmediata. |
| lag_7 | Venta en t−7 | Histórico o predicción previa; referencia semanal. |
| lag_28 | Venta en t−28 | Histórico para los 14 pasos; referencia de cuatro semanas. |
| Rolling mean 7 | Media de t−7 a t−1 | Histórico/predicciones; nivel reciente. |
| Rolling mean 28 | Media de t−28 a t−1 | Histórico/predicciones; nivel más estable. |
| Día de semana objetivo | Día de semana de t | Conocido de antemano; patrón semanal. |
| Producto categórico | item_id | Conocido; diferencias entre SKU, sin target encoding. |

Las medias móviles excluyen el objetivo también durante entrenamiento. Ninguna feature
puede usar una observación posterior al corte durante la generación multipaso.

### Exclusiones explícitas

| Variable excluida | Motivo |
|---|---|
| lag_14 | Referencia semanal adicional no imprescindible. |
| Mes | Evidencia insuficiente de un efecto anual repetible. |
| Fin de semana | Redundante con día de semana. |
| Tienda y departamento | Constantes en esta selección. |
| Precio | Disponibilidad operativa futura no demostrada; no necesario en V1. |
| Eventos/festivos | Pocas repeticiones para estimar sus efectos. |
| SNAP | Requiere justificar disponibilidad del calendario al corte. |
| Estadísticas globales con todo el histórico | Fuga de información futura. |

Día de semana, mes, fin de semana y eventos programados pueden conocerse de antemano;
su disponibilidad no obliga a incluirlos. Solo se utiliza día de semana en V1.

Un precio histórico conocido o un precio futuro planificado antes del corte sería
utilizable en otro protocolo. El precio futuro realizado del CSV no se presupone conocido.
Una bajada de precio no demuestra una promoción. Promociones no anunciadas, cierres
imprevistos, inventario futuro y ventas intermedias reales son información desconocida.

## 8. Series intermitentes e historia insuficiente

Se incluyen los 216 SKU, sin filtro mínimo de ventas. Todos tienen ventas positivas
en el entrenamiento inicial; FOODS_1_079 tiene solo nueve días positivos.

- Cero permanece como cero; no se transforma en missing.
- No se eliminan ceros anteriores a la primera venta: la fecha de introducción es desconocida.
- Una racha no implica automáticamente descatalogación, cierre o stockout.
- La actividad escasa se identifica en los resultados, sin prometer fiabilidad individual.
- Los segmentos se usan para evaluar, no para elegir retrospectivamente un modelo por SKU.
- Se exigen 28 días observados completos como contexto técnico.
- Con historia insuficiente se devuelve insufficient_history, sin inventar observaciones.
- Las predicciones conservan decimales; el redondeo de pedidos pertenece a reposición.

Los valores extremos válidos se conservan; no se aplica recorte automático por las
alertas descriptivas del estudio.

## 9. Métricas

Sea y(i,c,h) la venta observada del SKU i, con origen c y paso h, e y_hat su predicción.

| Papel | Métrica | Definición |
|---|---|---|
| Principal | RMSE del total de 14 días por SKU | Raíz de la media de errores acumulados cuadrados sobre pares SKU/corte. |
| Secundaria | WAPE diario | 100 × suma de errores absolutos diarios / suma de ventas observadas. |
| Secundaria | Bias porcentual | 100 × suma(predicho − observado) / suma de ventas observadas. |

Para la principal:

$$
E_{i,c}=\sum_{h=1}^{14}\hat y_{i,c,h}-\sum_{h=1}^{14}y_{i,c,h}
$$

$$
RMSE_{14}=\sqrt{\operatorname{media}_{i,c}(E_{i,c}^{2})}
$$

Se acumulan días dentro de cada SKU/corte antes de elevar al cuadrado. No se agregan
todos los SKU antes de calcular el error, ni se obtiene el resultado global promediando
los RMSE de los folds.

RMSE acumulado evalúa cantidades para planificación; WAPE diario mantiene visibilidad
sobre distribución temporal. Bias positivo indica sobrepredicción. MAE/WAPE diario no
gobiernan solos la selección: los errores absolutos favorecen la mediana, que puede ser
muy baja en estas series.

Se reportan resultados globales, por fold, por SKU entre folds y por segmentos de
volumen/intermitencia calculados con entrenamiento. WAPE diario se desglosa también
en pasos 1–7 y 8–14.

Si las ventas observadas del ámbito evaluado suman cero, RMSE permanece definido;
WAPE y Bias porcentual son indefinidos y se registran con denominador cero explícito.
Se conservan forecasts y errores en unidades. No se añade epsilon ni se ocultan casos.

WAPE global se calcula con sumas, no promediando porcentajes por SKU. No se presenta
100 − WAPE como accuracy. Estas métricas no demuestran costes ni nivel de servicio.

## 10. Política baseline frente a candidato

Ambos métodos utilizan los mismos productos, cortes, objetivos e información disponible.
La selección es global para el experimento.

El candidato se selecciona solo si cumple simultáneamente, en los seis folds de desarrollo:

1. RMSE acumulado global estrictamente menor que el baseline.
2. Mejora de RMSE acumulado en al menos cuatro folds.
3. Valor absoluto del Bias porcentual global no superior al del baseline.

En empate o incumplimiento, se conserva el baseline. No se seleccionan ganadores por SKU
de forma retrospectiva. La regla es conservadora, no una prueba de significación estadística.

Se congela la selección antes del test y se evalúan ambos métodos y la política elegida.
Un resultado desfavorable en test se informa sin cambiar retrospectivamente la decisión.
Una revisión constituye otro protocolo experimental, no una reinterpretación del test.

El método seleccionado alimentará la futura reposición; esta selección no demuestra
optimalidad de inventario.

## 11. Salidas, trazabilidad y coste

Cada ejecución debe conservar:

- run_id, tipo de ejecución, estado, timestamps, duración y errores.
- Fuente, cargas utilizadas y huella de los datos.
- Selección, rango de entrenamiento, corte y horizonte.
- Versión de protocolo (1.0), código, features, dependencias, configuración y semilla.
- Forecast por SKU, tienda, origen, fecha objetivo, paso y unidades previstas.
- Métricas de baseline y candidato con ámbito de agregación.
- Método seleccionado y motivo.
- Artefacto del modelo y checksum, cuando exista.

Entrenamiento, evaluación y forecast final se distinguen en la trazabilidad.
Los resultados publicados deben pertenecer a una ejecución completa; un fallo no
reemplaza la última publicación válida. El esquema SQL queda para implementación.

Con 28 días de contexto se obtienen unas 82.512 filas supervisadas en el primer
entrenamiento y 103.680 en el ajuste con todo el histórico. Cada método produce
3.024 predicciones por origen. Es un volumen manejable con pandas y CPU; tiempos y
memoria se medirán sin extrapolar el coste de ingesta ni optimizar preventivamente.
Los tests usan controles pequeños, no el dataset completo.

## 12. Limitaciones y riesgos

- Las ventas pueden estar censuradas por disponibilidad desconocida.
- Los cambios de nivel y rachas largas limitan la representatividad del pasado.
- Una fuga multipaso produciría resultados artificialmente favorables.
- La recursión puede deteriorar especialmente la segunda semana.
- RMSE da mayor peso a errores grandes; deben revisarse SKU y segmentos.
- Seis folds y un test de dos semanas no acreditan rendimiento anual ni en otras tiendas.
- El test ya tuvo inspección descriptiva; no es un conjunto nunca observado.
- Poisson no garantiza una distribución de ventas ni intervalos de incertidumbre.
- Los ceros, eventos y precios no permiten establecer causalidad.
- El forecast final posterior a 2016-05-22 carece de objetivos en el CSV actual.

## 13. Definition of Done

Forecasting V1 estará terminado cuando:

1. El protocolo, configuración y datos estén versionados e identificados.
2. Existan el baseline y el único candidato, con resultados comparables.
3. Los seis folds y el test reproduzcan los 14 pasos sin observaciones futuras.
4. Haya pruebas de aislamiento temporal, ventanas desplazadas, recursión, ceros y métricas.
5. Se registren métricas globales, por fold, SKU y segmento, incluidos casos indefinidos.
6. La selección se congele antes del test y su resultado se conserve sin selección retrospectiva.
7. Forecasts, métricas, artefactos y procedencia queden persistidos y sean reproducibles.
8. Los fallos no sustituyan resultados publicados válidos.
9. Se documenten comportamiento, ejemplos, errores, limitaciones, tiempos y memoria.
10. La fase pueda completarse aunque el candidato no supere al baseline.

La aceptación del protocolo no implica que estas funcionalidades estén implementadas.

## Referencias

- [Evaluación temporal con origen móvil](https://otexts.com/fpp3/tscv.html).
- [HistGradientBoostingRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html).
- [Propiedades y limitaciones de WAPE](https://robjhyndman.com/hyndsight/wape.html).
