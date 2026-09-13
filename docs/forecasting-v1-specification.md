# DemandIQ — Especificación propuesta de Forecasting V1

**Recomiendo conservar CA_1 / FOODS_1 y los 508 días para el primer experimento**, con horizonte de 14 días, un baseline semanal suavizado y un único candidato global.

Esta propuesta se apoya en el análisis real ya realizado sobre PostgreSQL y los CSV. No he implementado forecasting, creado features definitivas, ampliado la ingesta ni añadido librerías.

## 1. Perfil estadístico del subconjunto actual

### Distribución de las ventas

| Indicador | Resultado |
|---|---:|
| SKU | 216 |
| Observaciones | 109.728 |
| Unidades totales | 169.836 |
| Media de unidades por SKU/día | 1,548 |
| Mediana | 0 |
| Desviación estándar | 2,933 |
| Percentil 95 | 7 unidades |
| Percentil 99 | 14 unidades |
| Máximo diario de un SKU | 92 unidades |
| Mediana de las medias diarias por SKU | 0,929 |
| Rango de medias diarias por SKU | 0,031–10,451 |

Hay diferencias importantes entre productos:

- `FOODS_1_099`: **5.309 unidades**, media de 10,45 al día.
- `FOODS_1_079`: **16 unidades**, con ventas positivas en solo 11 días.
- Los diez SKU de mayor volumen concentran **25,1 %** de las unidades.

### Segmentos de volumen

Para describirlos, utilicé tres grupos de 72 productos ordenados por ventas acumuladas. Son **terciles relativos al subconjunto**, no categorías empresariales definitivas.

| Tercil | Media diaria por SKU | Participación en ventas | Días con cero |
|---|---:|---:|---:|
| Superior | 1,309–10,451 | 69,59 % | 27,93 % |
| Intermedio | 0,715–1,291 | 20,90 % | 51,77 % |
| Inferior | 0,031–0,711 | 9,51 % | 72,59 % |

En backtesting, la pertenencia a segmentos se calculará **solo con el entrenamiento disponible en cada corte**.

### Intermitencia y actividad

| Condición | SKU |
|---|---:|
| Al menos 50 % de días con cero | 114 |
| Al menos 75 % | 27 |
| Al menos 90 % | 6 |
| Al menos 95 % | 1 |
| Sin ninguna venta durante los 508 días | 0 |
| Alguna racha de al menos 28 ceros | 109 |
| Alguna racha de al menos 90 ceros | 50 |
| Alguna racha de al menos 180 ceros | 16 |

La mediana del porcentaje de ceros por SKU es **51,87 %**. La mayor racha alcanza **379 días**, en `FOODS_1_102`.

Los 508 días están completos, pero los días con venta positiva varían entre **11 y 505**. Por tanto, longitud observada y cantidad de información sobre actividad no son equivalentes.

Los umbrales anteriores describen intermitencia; no justifican por sí solos excluir productos o declararlos descatalogados.

### Patrones temporales

Analizando separadamente el entrenamiento inicial propuesto, hasta el **14/02/2016**:

- El agregado promedia aproximadamente **289 unidades los martes** y **425 los sábados**.
- **167 SKU** presentan mayor venta media durante el fin de semana.
- La autocorrelación semanal del agregado es aproximadamente **0,51**.
- La señal semanal individual es bastante desigual.

Hay diferencias mensuales: mayo de 2015 promedia **399 unidades diarias**, frente a **231 en noviembre**. No podemos atribuirlas automáticamente a estacionalidad anual.

Entre los primeros y últimos 56 días del entrenamiento inicial, el volumen agregado disminuye aproximadamente **12,5 %**. También hay cambios locales: `FOODS_1_004` pasa de **10,4 a 21,8 unidades diarias** entre dos ventanas consecutivas de 28 días.

### Valores extremos

Una regla exploratoria conservadora identifica **94 observaciones inusuales en 56 SKU** del entrenamiento inicial. No son errores demostrados.

El máximo de 92 unidades corresponde a `FOODS_1_218` el 14/02/2015. Lo conservaría.

El 25/12/2015 todos los SKU registran cero y el calendario identifica Christmas. No convertiría esa coincidencia en una regla de cierre sin información adicional.

Los diagnósticos completos están en [forecasting-data-profile.json](../artifacts/forecasting-data-profile.json).

## 2. ¿Mantener o ampliar los 508 días?

**Mantenerlos para V1.**

Permiten aprender relaciones semanales y disponer de varios cortes temporales. El entrenamiento del primer fold contendría **410 días**, unas 58 semanas.

| Alternativa | Días por SKU | Observaciones |
|---|---:|---:|
| Periodo actual | 508 | 109.728 |
| Ampliar desde 2014-01-01 | 873 | 188.568 |
| Histórico completo disponible | 1.941 | 419.256 |

La ampliación sería manejable para PostgreSQL y pandas. Sin embargo:

- No necesitamos modelar estacionalidad anual en este primer experimento.
- Más historia puede incorporar regímenes comerciales antiguos.
- En 2014, dos de estos productos no tienen ninguna venta positiva.
- La señal profesional depende más de una evaluación correcta que de aumentar filas.

No ampliaría ni recortaría historia basándome en el resultado del test final.

## 3. Horizonte recomendado

**14 días, con salida diaria por SKU.**

| Horizonte | Evaluación |
|---|---|
| 7 días | Sencillo, pero potencialmente corto para una futura política de reposición. |
| **14 días** | Dos ciclos semanales y compromiso razonable entre utilidad e incertidumbre. |
| 28 días | Mayor dificultad multipaso; no hay todavía una necesidad operativa que lo exija. |

Esto no fija el lead time ni el review period.

Posteriormente, si su suma supera 14 días, el forecast no cubrirá todo el periodo de protección. Habrá que revisar el horizonte; no extrapolar automáticamente.

## 4. Protocolo temporal recomendado

**Ventana expansiva desde 2015-01-01, seis folds de desarrollo y un test final.**

| Etapa | Corte: último día observado | Periodo pronosticado |
|---|---|---|
| Fold 1 | 2016-02-14 | 2016-02-15 → 2016-02-28 |
| Fold 2 | 2016-02-28 | 2016-02-29 → 2016-03-13 |
| Fold 3 | 2016-03-13 | 2016-03-14 → 2016-03-27 |
| Fold 4 | 2016-03-27 | 2016-03-28 → 2016-04-10 |
| Fold 5 | 2016-04-10 | 2016-04-11 → 2016-04-24 |
| Fold 6 | 2016-04-24 | 2016-04-25 → 2016-05-08 |
| **Test** | **2016-05-08** | **2016-05-09 → 2016-05-22** |

Todos los SKU comparten cortes. Las ventanas de evaluación no se solapan.

Reglas:

- El corte representa el cierre del día, con ventas completas disponibles.
- Se reajusta el candidato en cada fold.
- Se generan los 14 días sin introducir ventas reales posteriores al corte.
- El siguiente fold puede incorporar observaciones anteriores que ya serían conocidas.
- Codificaciones, selección de segmentos y cualquier transformación ajustable utilizan únicamente entrenamiento.
- No hay separación aleatoria.
- No hay ajuste de hiperparámetros usando el test.

Este procedimiento reproduce una evaluación con origen temporal móvil y varios pasos futuros. [Referencia metodológica](https://otexts.com/fpp3/tscv.html).

El test queda reservado para comparar modelos **desde ahora**. Ya hubo auditoría y análisis descriptivo del histórico completo; debemos reconocerlo y no presentarlo como un conjunto nunca examinado.

Después del test, se puede reajustar el método seleccionado con los 508 días y pronosticar **2016-05-23 → 2016-06-05**. Ese forecast final no tendrá valores observados disponibles en nuestro CSV para evaluarlo.

## 5. Baseline recomendado

**Media de las cuatro últimas observaciones del mismo día de la semana.**

Para pronosticar un lunes, se promedian los cuatro lunes más recientes conocidos en el corte. El patrón se repite durante las dos semanas futuras.

Lo elegiría porque:

- Aprovecha el patrón semanal observado.
- Reduce la sensibilidad a un único cero o pico.
- Conserva los ceros dentro del cálculo.
- Es explicable sin ML.
- Solo requiere 28 días de contexto.

El último valor sería demasiado inestable. La media general reciente pierde el efecto del día de semana. El naïve semanal puro depende excesivamente de una sola observación.

No añadiría otros baselines inicialmente.

## 6. Modelo candidato recomendado

**Un `HistGradientBoostingRegressor` global con pérdida Poisson**, compartido por los 216 productos.

Puede aprender relaciones no lineales entre actividad reciente, calendario e identidad del SKU. La pérdida admite objetivos cero y utiliza enlace logarítmico, adecuado para estimaciones medias positivas. El soporte categórico permite representar los 216 productos dentro del límite actual de 255 categorías por variable. [Documentación oficial](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html).

Esto no significa que las ventas sigan una distribución Poisson: muestran dispersión elevada. Tampoco resuelve automáticamente la intermitencia ni identifica stockouts.

**Estrategia:** entrenamiento a un paso y forecast recursivo de 14 días. Las predicciones anteriores sustituyen a las observaciones futuras todavía desconocidas.

Configuración inicial propuesta, sin búsqueda de hiperparámetros:

- 100 iteraciones.
- Learning rate 0,1.
- Máximo de 15 hojas.
- Mínimo de 50 muestras por hoja.
- Semilla fija.
- *Early stopping* desactivado, evitando una validación interna aleatoria.

Son parámetros iniciales conservadores, no valores optimizados.

Descartaría inicialmente:

- Modelos separados por SKU: fragmentan la información.
- Modelos lineales: exigirían especificar más interacciones manualmente.
- Random Forest: mayor tamaño potencial sin una ventaja demostrada aquí.
- Otros frameworks: dependencia adicional innecesaria.

La interpretación será mediante variables utilizadas, ejemplos y errores por segmento. No presentaremos explicaciones causales de cada forecast.

## 7. Features iniciales

| Feature | Disponibilidad durante el forecast | Utilidad y riesgo |
|---|---|---|
| `lag_1` | Histórico o predicción previa | Actividad inmediata; nunca usar la venta futura real. |
| `lag_7` | Histórico o predicción previa | Referencia semanal. |
| `lag_28` | Histórico para todos los 14 pasos | Referencia de cuatro semanas atrás. |
| Rolling mean 7 | Histórico y, cuando corresponda, predicciones | Nivel reciente; excluir siempre el objetivo. |
| Rolling mean 28 | Histórico y predicciones | Nivel más estable. |
| Día de semana objetivo | Conocido de antemano | Diferencias semanales observadas. |
| Producto categórico | Conocido | Diferencias entre SKU, sin target encoding. |

Los lags se definen respecto al día objetivo. Durante entrenamiento, las medias móviles deben estar desplazadas para no incluir ese día.

Excluiría inicialmente:

- `lag_14`: otra referencia semanal no imprescindible.
- Mes: evidencia insuficiente de un efecto anual repetible.
- Fin de semana: redundante con día de semana.
- Tienda y departamento: constantes.
- Precio y eventos: pendientes de las condiciones indicadas en el apartado 11.

No añadiría estadísticas globales del SKU calculadas usando todo el histórico.

## 8. Tratamiento de series intermitentes

**Incluir los 216 SKU y segmentar para evaluar, sin filtro mínimo de ventas.**

Todos tienen alguna venta positiva en el entrenamiento inicial. El caso más extremo, `FOODS_1_079`, tiene nueve días positivos en ese periodo.

Reglas:

- No convertir cero en missing.
- No eliminar ceros anteriores a la primera venta: desconocemos la fecha real de introducción comercial.
- No declarar automáticamente descatalogación o stockout por una racha.
- Identificar actividad escasa en los resultados, sin prometer fiabilidad individual.
- Exigir 28 días completos como mínimo técnico para este experimento.
- Si no hay suficiente historia, devolver `insufficient_history`, sin inventar observaciones.
- Mantener los forecasts decimales: el redondeo de pedidos pertenece a reposición.

Excluir productos difíciles podría mejorar las métricas mientras empeora la representatividad del proyecto.

## 9. Métricas

**Cambiaría la prioridad inicialmente planteada.**

MAE y WAPE diario favorecen estimaciones de la mediana. En series intermitentes, eso puede premiar forecasts muy bajos aunque nos interese estimar cantidades medias para planificación. WAPE también resulta indefinido cuando su denominador es cero. [Referencia sobre WAPE](https://robjhyndman.com/hyndsight/wape.html).

Propongo tres métricas:

| Papel | Métrica |
|---|---|
| **Principal** | **RMSE del total de 14 días por SKU** |
| Secundaria | WAPE diario |
| Secundaria | Bias porcentual |

Para la principal, primero calculamos por SKU y corte:

$$
E_{i,c}=\sum_{h=1}^{14}\hat y_{i,c,h}-\sum_{h=1}^{14}y_{i,c,h}
$$

Después:

$$
RMSE_{14}=\sqrt{\operatorname{media}_{i,c}(E_{i,c}^{2})}
$$

Así evitamos que errores de distintos productos se cancelen antes de evaluarlos.

El WAPE diario conserva visibilidad sobre errores de distribución temporal. El Bias utiliza `predicho − observado`: positivo significa sobrepredicción.

Reportaría resultados:

- Globales y por fold.
- Por terciles de volumen e intermitencia.
- Por SKU entre folds.
- WAPE diario para pasos 1–7 y 8–14.

Cuando las ventas observadas sumen cero:

- RMSE continúa definido.
- WAPE y Bias porcentual se registran como indefinidos, con denominador cero explícito.
- Se conservan el forecast y los errores en unidades.
- No se añade un epsilon artificial.

No promediaría porcentajes WAPE individuales para obtener el global. Tampoco usaría `100 − WAPE` como accuracy.

## 10. Regla baseline/candidato

Mismos productos, fechas, información disponible y procedimiento de evaluación.

Seleccionaría el candidato solo si, en los seis folds:

1. Reduce el RMSE acumulado global.
2. Mejora esa métrica en al menos cuatro folds.
3. No empeora el valor absoluto del Bias porcentual global.

En empate o incumplimiento, se conserva el baseline.

Es una política conservadora definida antes de ejecutar, no una prueba estadística de superioridad. La elección será global, sin seleccionar ganadores retrospectivos por SKU.

Después se congela la política y se evalúa en el test. Si allí pierde, se informa; no se cambia retrospectivamente la decisión.

La política determinará qué forecast queda seleccionado para el futuro módulo de reposición. Aún no demuestra que una política de inventario sea óptima.

## 11. Datos adicionales necesarios: precio y calendario

### Precio

**Lo excluiría del primer candidato.**

| Información | Disponibilidad |
|---|---|
| Precio histórico conocido al corte | Utilizable. |
| Precio futuro planificado y registrado antes del corte | Utilizable si existe ese registro operativo. |
| Precio futuro realizado del CSV | No asumir que era conocido en producción. |
| Bajadas históricas de precio | Observables; no equivalen automáticamente a promociones identificadas. |

No necesitamos ingerir precios para demostrar correctamente este experimento.

### Calendario

**KNOWN IN ADVANCE:**

- Día de semana.
- Mes.
- Fin de semana.
- Fechas de festivos y eventos programados.

Solo incluiría día de semana inicialmente.

**Disponibilidad que requiere justificar:**

- SNAP: habría que documentar que el indicador representa un calendario conocido en el corte.
- Promociones planificadas: requerirían información operativa previa.

**UNKNOWN / POTENTIAL LEAKAGE:**

- Promociones futuras no anunciadas.
- Cierres imprevistos.
- Inventario futuro.
- Ventas reales intermedias dentro del horizonte.

Los eventos programados son legítimos temporalmente, pero tenemos pocas repeticiones para aprender sus efectos con confianza.

## 12. Definition of Done de Forecasting V1

La fase se considera terminada cuando:

- Existe un protocolo versionado con cortes, horizonte y configuración.
- Baseline y candidato generan resultados comparables.
- Los 14 pasos se evalúan sin observaciones futuras.
- Hay pruebas relevantes de aislamiento temporal, rolling windows, recursión, ceros y métricas.
- Se registran métricas globales, por fold y segmento.
- La selección se congela antes del test.
- El resultado del test se conserva sin selección retrospectiva.
- Forecasts, métricas y procedencia quedan persistidos.
- Una ejecución fallida no reemplaza una publicación válida.
- Se documentan reproducibilidad, duración y limitaciones.
- El candidato puede perder sin impedir completar la fase.

Cada ejecución debe conservar:

- `run_id`, tipo, estado y timestamps.
- Fuente, cargas y huella de los datos utilizados.
- Selección, entrenamiento, corte y horizonte.
- Versiones de protocolo, código, features y dependencias.
- Configuración y semilla.
- Forecast por SKU, tienda, origen, fecha objetivo y paso.
- Métricas de ambos métodos.
- Método seleccionado y motivo.
- Artefacto del modelo con checksum, cuando corresponda.
- Errores y duración.

No hace falta cerrar todavía las tablas SQL.

**Coste:** aproximadamente 82.512 filas supervisadas en el primer entrenamiento y 103.680 en el ajuste con todo el histórico, descontando 28 días iniciales de contexto. Cada método produce 3.024 predicciones por origen.

Es un tamaño razonable para pandas y entrenamiento en CPU. Los tiempos deberán medirse; no extrapolaría el tiempo de ingesta al entrenamiento. Los tests seguirán utilizando ejemplos pequeños.

## 13. Riesgos principales

1. **Ventas distintas de demanda no restringida:** no conocemos las ventas perdidas.
2. **Leakage multipaso:** introducir datos reales intermedios falsearía el experimento.
3. **Cambios de nivel y disponibilidad desconocida:** limitan lo que puede aprenderse del histórico.
4. **Peso de los SKU grandes en RMSE:** obliga a revisar segmentos y productos.
5. **Generalización limitada:** seis ventanas y un test de dos semanas no representan un año completo.
6. **Error recursivo:** alimentar predicciones anteriores puede deteriorar la segunda semana.

La pérdida Poisson no elimina estos riesgos ni proporciona automáticamente intervalos de incertidumbre.

## 14. Decisiones que debemos confirmar antes de implementar

La propuesta queda concretada en:

- **Datos:** mantener CA_1 / FOODS_1 y los 508 días.
- **Horizonte:** 14 días, salida diaria.
- **Evaluación:** seis folds expansivos y el test indicado.
- **Baseline:** media de cuatro observaciones del mismo día semanal.
- **Candidato:** un HistGradientBoostingRegressor global, Poisson y recursivo.
- **Features:** las siete propuestas.
- **Intermitencia:** mantener todos los SKU, sin filtro por ventas.
- **Métricas:** RMSE acumulado principal, WAPE diario y Bias secundarios.
- **Selección:** regla fijada con los folds, antes del test.
- **Datos auxiliares:** sin precios, eventos ni SNAP inicialmente.

**No faltan datos ni hay un bloqueo técnico para esta especificación.** Queda confirmar este conjunto de decisiones antes de programar. El estado siguiente significa que la propuesta experimental está completa, no que haya empezado su implementación.

FORECASTING SPECIFICATION READY
