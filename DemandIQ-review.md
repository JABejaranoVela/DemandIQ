## 1. VEREDICTO GENERAL

**DemandIQ tiene sentido para tu perfil y lo elegiría antes que un tercer full-stack similar a los anteriores.** El problema empresarial es real y permite demostrar una capacidad que tus otros proyectos cubren menos: convertir datos en decisiones mediante un sistema reproducible.

Su valor diferencial estaría en conectar:

- Datos con problemas de calidad.
- Transformaciones y modelado SQL.
- Predicciones evaluadas honestamente.
- Reglas de negocio explicables.
- Resultados accesibles mediante API y BI.

Frente a otro proyecto con embeddings, amplía más tu perfil. Frente a un notebook aislado, permite demostrar que sabes integrar el análisis dentro de un sistema de software.

**La principal reserva es el alcance:** forecasting, inventario y reposición pueden convertirse en tres proyectos diferentes si intentas resolverlos con profundidad empresarial completa.

También ajustaría la promesa: inicialmente lo describiría como un **sistema de apoyo a decisiones de reposición**, con recomendaciones sujetas a datos y supuestos explícitos. La expresión «plataforma» puede crear expectativas de interfaz operativa, usuarios, proveedores y gestión de pedidos que no necesitas cubrir.

## 2. ARQUITECTURA

Mantendría prácticamente todas las decisiones estructurales, con algunos ajustes.

| Decisión | Valoración |
|---|---|
| Monolito modular | Adecuado para una persona y este alcance. |
| Pipeline batch | Encaja con decisiones periódicas de inventario. |
| Forecasting separado de replenishment | Fundamental: estimación estadística y política empresarial cambian por motivos distintos. |
| Batch separado de serving | Correcto: consultar resultados debe ser rápido y predecible. |
| PostgreSQL | Suficiente para datos operativos, transformaciones y consumo analítico de esta escala. |
| FastAPI | Adecuado para exponer resultados e integración con otros sistemas. |
| Power BI | Complementa la API con análisis y presentación del negocio. |

**Cambiaría cuatro aspectos conceptuales:**

1. **Un único proyecto Python, con ejecuciones distintas para API y batch.** Pueden compartir paquete e imagen Docker. Separar procesos no implica introducir microservicios.

2. **El pipeline coordina los módulos; no concentra toda la lógica.** Forecasting calcula predicciones y reposición aplica políticas. Ninguno debería necesitar llamar a la API.

3. **Separaría entrenamiento, evaluación y generación de predicciones.** Aunque inicialmente puedan ejecutarse juntos, no deberían estar acoplados: generar nuevas predicciones no exige siempre reentrenar.

4. **Publicaría únicamente ejecuciones completas.** API y BI deben poder identificar qué ejecución consumen. Si falla la reposición tras calcular forecasts, no debería aparecer una mezcla de resultados nuevos y antiguos como si fuera coherente.

Existe una limitación de producto que conviene reconocer: **FastAPI no constituye una interfaz utilizable por un responsable de tienda.** Para el portfolio, una API demostrable y un informe BI son suficientes. Para venderlo como producto operativo, faltaría una experiencia de usuario. No añadiría ahora un frontend para resolver esa diferencia.

## 3. STACK

**Mantendría el stack; cambiaría algunos usos y expectativas.**

| Tecnología | Decisión | Justificación |
|---|---|---|
| Python 3.13 | MANTENER | Es una elección razonable. Sustituir «aproximadamente» por una versión concreta al implementar. |
| FastAPI | MANTENER | Ya lo conoces y encaja con una API de consulta. |
| Pydantic | MANTENER | Contratos y validación en los límites del sistema. |
| pydantic-settings | MANTENER | Configuración centralizada y tipada. |
| PostgreSQL | MANTENER | Evita incorporar otro motor para una carga que puede resolver. |
| SQLAlchemy 2 | MANTENER | Útil para persistencia; no obligaría a expresar todas las transformaciones mediante ORM. |
| Alembic | MANTENER | Migraciones también para estructuras analíticas persistidas. |
| Psycopg 3 | MANTENER | Coherente con PostgreSQL y el resto del stack. |
| pandas | MANTENER | Exploración, preparación de series y features. |
| NumPy | MANTENER | Cálculos numéricos cuando aporten claridad. |
| scikit-learn | MANTENER | Suficiente para un candidato basado en variables temporales. |
| Power BI | MANTENER | Principal ampliación hacia BI y análisis de negocio. |
| pytest | MANTENER | Base común del testing. |
| HTTPX | MANTENER | Pruebas de la API. |
| Schemathesis | MANTENER, ACOTADO | Complemento para contratos; no sustituye pruebas del negocio. |
| Ruff | MANTENER | Evita fragmentar lint y formato en varias herramientas. |
| uv | MANTENER | Entornos y dependencias con un flujo sencillo. |
| pyproject.toml / uv.lock | MANTENER | Configuración y resolución reproducible de dependencias. |
| Docker / Compose | MANTENER | Ejecución local y despliegue consistentes. |
| GitHub Actions / GHCR | MANTENER | Aprovecha experiencia existente. |
| VPS Ubuntu / Nginx | MANTENER | Infraestructura suficiente y conocida. |
| Git / GitHub | MANTENER | Versionado, revisión y presentación del proyecto. |

La documentación de scikit-learn confirma soporte de Python 3.13 en versiones de la biblioteca; comprobaría el conjunto completo de dependencias al fijarlas, sin bajar preventivamente a otra versión. [Compatibilidad de scikit-learn](https://scikit-learn.org/stable/install.html).

uv permite conservar la resolución de dependencias mediante el lockfile. Su valor aquí es la reproducibilidad, más que incorporar una herramienta «moderna». [Documentación de uv](https://docs.astral.sh/uv/concepts/projects/sync/).

**CAMBIAR:** usar SQL para transformaciones relacionales y cargas por lotes cuando corresponda; evitar procesar grandes ingestas registro a registro con el ORM.

**ELIMINAR:** ninguna tecnología esencial de la propuesta. Mantendría fuera las tecnologías que ya has excluido.

**AÑADIR:** solamente un mecanismo sencillo de ejecución periódica del batch, como un temporizador del sistema operativo. No justifica introducir un orquestador especializado.

## 4. COMPLEJIDAD

La arquitectura no está sobrediseñada por sí misma. **El riesgo está en desarrollar cada bloque como si fuera una plataforma independiente.**

Evitaría:

- Frameworks internos de pipelines y repositorios genéricos.
- Arquitectura hexagonal ceremonial con múltiples interfaces por operación.
- Gestión completa de proveedores y órdenes de compra.
- Multiempresa, permisos complejos y autenticación para demostrar algo que tus proyectos anteriores ya cubren.
- Un modelo y ajuste de hiperparámetros independiente para cada producto.
- Duplicar todas las tablas en tres capas sin una transformación o responsabilidad concreta.
- Un panel para cada pregunta empresarial de la lista inicial.

Un módulo puede comenzar con unas pocas funciones y estructuras bien definidas. **La profesionalidad se demuestra en límites claros y comportamiento verificable, no en cantidad de carpetas.**

## 5. CARENCIAS

Veo cinco carencias importantes que no requieren ampliar mucho el stack:

1. **Trazabilidad de las ejecuciones.** Qué datos se utilizaron, hasta qué fecha, con qué configuración y versión del modelo, y si la ejecución terminó correctamente.

2. **Reejecución segura.** Cargar dos veces los mismos datos no debe duplicar ventas ni recomendaciones. Una corrección de origen debe poder procesarse de forma controlada.

3. **Vigencia de los resultados.** Una recomendación necesita indicar la fecha del inventario y del forecast. Que la API responda no implica que sus datos estén actualizados.

4. **Tratamiento explícito de datos insuficientes.** Ausencias, productos nuevos o inventario desconocido deben generar un resultado comprensible, no cifras aparentemente precisas.

5. **Explicación de la recomendación.** Mostrar qué stock, previsión y política llevaron a sugerir una cantidad.

Con estas cinco propiedades, el proyecto se parecerá mucho más a un sistema empresarial que añadiendo otra herramienta.

## 6. DATA ENGINEERING

**RAW → CORE → ANALYTICS tiene sentido dentro de PostgreSQL**, siempre que cada capa tenga una responsabilidad observable.

| Capa | Responsabilidad |
|---|---|
| RAW | Conservar lo recibido y su procedencia para poder revisar o reprocesar. |
| CORE | Representar datos de negocio limpios, con claves, tipos y reglas consistentes. |
| ANALYTICS | Ofrecer estructuras de consulta para análisis, forecasts y recomendaciones. |

La capa RAW no debe ser una copia de CORE con otro nombre. Conviene conservar identificación de la carga, origen y registros rechazados. Si necesitas preservar el archivo exacto, una tabla convertida a tipos SQL puede no bastar; el mecanismo concreto depende del formato que decidáis después.

En ANALYTICS empezaría con **vistas cuando sean suficientes** y tablas para resultados que deban conservarse históricamente. No materializaría todo por anticipación.

La propuesta dimensional también es razonable. Microsoft recomienda organizar modelos de Power BI mediante hechos y dimensiones con granularidad consistente. [Guía de esquema en estrella](https://learn.microsoft.com/en-us/power-bi/guidance/star-schema).

Los errores que más vigilaría son:

- Sumar snapshots de inventario entre fechas como si fueran ventas.
- Duplicar ventas al unirlas con varias ejecuciones de forecast.
- Comparar predicción y realidad con distinta granularidad.
- Confundir importe vendido con unidades vendidas.

No necesitas Spark para demostrar Data Engineering. **Una carga idempotente, transformaciones SQL correctas y trazabilidad tienen valor técnico real.**

## 7. FORECASTING

**La estrategia es correcta.** Baseline, candidato sencillo y evaluación temporal es una base defendible.

No cerraría todavía los algoritmos. Antes comprobaría regularidad, longitud de las series, estacionalidad, ceros y disponibilidad de variables.

### El matiz más importante: ventas no equivalen siempre a demanda

Si un producto estuvo agotado, las ventas observadas pueden ser inferiores a lo que los clientes habrían comprado.

Por tanto:

- Con datos de disponibilidad puedes identificar parte de esa limitación.
- Sin ellos, estarás prediciendo ventas observadas como aproximación a demanda.
- No deberías afirmar que recuperas demanda perdida sin un método y evidencia para hacerlo.

### Evaluación temporal

Recomendaría varios cortes temporales y una evaluación final reservada. Además, la evaluación debe reproducir la distancia de predicción que utilizará el negocio: acertar el siguiente periodo no demuestra acertar todos los periodos necesarios para reponer. [Evaluación temporal de forecasting](https://otexts.com/fpp3/tscv.html).

Los riesgos concretos de fuga de información son:

- Medias móviles que incluyen el valor objetivo.
- Lags calculados mezclando productos o ubicaciones.
- Transformaciones ajustadas con datos de evaluación.
- Precios o promociones futuros que no eran conocidos al emitir la predicción.
- Usar ventas reales intermedias para evaluar un forecast de varios pasos que, en producción, no las tendría disponibles.

El ejemplo oficial de scikit-learn respalda el enfoque de features retardadas y muestra por qué una partición aleatoria produce resultados demasiado optimistas. No necesitas incorporar las otras bibliotecas del ejemplo. [Forecasting con variables retardadas](https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html).

### Métricas

| Métrica | Valoración |
|---|---|
| MAE | Mantener: expresa el error en unidades comprensibles. |
| WAPE | Mantener como resumen agregado, con cautela. |
| Bias | Mantener: muestra tendencia a sobrepredecir o infrapredecir. |
| RMSE | Secundaria, si interesa destacar errores grandes. |

WAPE no está definida si el total observado es cero y puede resultar engañosa al comparar ventanas con niveles de ventas diferentes. No la usaría como único criterio de calidad. MASE o RMSSE podrían estudiarse después si aparece una necesidad concreta de comparación entre series; no las añadiría automáticamente. [Análisis de WAPE de Rob Hyndman](https://robjhyndman.com/hyndsight/wape.html).

También mostraría resultados por segmentos: un agregado bueno puede ocultar productos mal predichos. Definiría el signo de Bias explícitamente y evitaría llamar «precisión» a `100 − WAPE`.

**Que el candidato no supere al baseline no invalida el proyecto.** Lo invalida presentar una mejora inexistente o hacer una comparación injusta.

## 8. REPLENISHMENT

Mantendría una separación estricta de responsabilidades:

| Forecasting | Replenishment |
|---|---|
| Estima ventas o demanda futura por periodo. | Convierte previsiones y estado del inventario en una propuesta. |
| Se evalúa contra observaciones posteriores. | Se evalúa contra reglas y objetivos de inventario. |
| No decide cuánto comprar. | No necesita conocer el algoritmo que produjo la previsión. |

**Variables mínimas conceptuales:**

- Demanda prevista durante el periodo que se quiere cubrir.
- Stock utilizable en una fecha conocida.
- Tiempo hasta recibir una reposición.
- Frecuencia con la que se revisa o permite pedir.
- Política de protección frente a incertidumbre.
- Compromisos y entradas pendientes, cuando existan.

La corrección principal a vuestra fórmula es que **cubrir solamente el lead time puede ser insuficiente si los pedidos se revisan periódicamente**. En ese caso también importa el tiempo hasta la siguiente oportunidad de revisión.

También distinguiría:

- **Stock físico:** lo que hay.
- **Stock disponible:** lo utilizable después de reservas o bloqueos.
- **Posición de inventario:** incorpora entradas y compromisos según la política utilizada.

Podéis excluir pedidos en tránsito inicialmente, pero entonces la recomendación depende de una hipótesis explícita. No tener ese dato no equivale a saber que no existen pedidos.

Otros dos límites relevantes:

- Una cantidad para cubrir el futuro no resuelve necesariamente una rotura que ocurrirá antes de que llegue el pedido.
- Un «riesgo de rotura» basado en cobertura es una señal determinista; no debe presentarse como una probabilidad calibrada.

No fijaría todavía fórmula, representación del lead time ni stock de seguridad. Tampoco introduciría optimización de compras, presupuestos o múltiples proveedores.

## 9. POWER BI

**Lo mantendría. Es probablemente la incorporación con mayor valor diferencial respecto a tus otros proyectos.**

Pero debe demostrar algo más que gráficos:

- Modelo de relaciones coherente.
- Medidas bien definidas.
- Agregaciones correctas.
- Contexto temporal.
- Capacidad de explicar una decisión empresarial.

Import Mode encaja con un pipeline batch y un volumen acotado. El conector PostgreSQL admite Import y DirectQuery; no veo una razón inicial para elegir el segundo. [Conector oficial PostgreSQL](https://learn.microsoft.com/en-us/power-query/connectors/postgresql).

Distribuiría responsabilidades así:

- **SQL/Python:** limpieza, reglas compartidas, predicciones y recomendaciones.
- **Power BI/DAX:** medidas analíticas y comportamiento de los cálculos bajo filtros.

No duplicaría la política de reposición en DAX.

**Hay una complejidad de distribución que conviene anticipar:** crear un informe en Desktop y compartirlo con actualización automática en Power BI Service son asuntos distintos. La compartición depende de licencias y capacidad; una conexión que requiera gateway añade infraestructura, y el gateway local es una aplicación Windows. No asumiría que queda resuelto con el VPS Ubuntu. [Licencias](https://learn.microsoft.com/en-us/power-bi/fundamentals/service-features-license-type), [gateway](https://learn.microsoft.com/en-us/data-integration/gateway/service-gateway-onprem).

Para validar el proyecto no haría depender su finalización de una publicación online automatizada del informe.

## 10. TESTING

El enfoque es bueno. **Priorizaría errores de datos, tiempo y negocio sobre multiplicar categorías de tests.**

| Tipo | Qué merece comprobarse |
|---|---|
| Unitarios | Cálculos de cobertura, reglas de reposición, métricas y casos límite. |
| Validación de datos | Duplicados, claves desconocidas, fechas inválidas y distinción entre cero y ausencia. |
| Integración con PostgreSQL | Restricciones, transacciones, reingesta y publicación consistente. |
| Forecasting | Features sin información futura y evaluación que reproduce la predicción real. |
| API | Contratos, filtros, ausencia de resultados y metadatos de vigencia. |
| Schemathesis | Entradas inesperadas e incumplimientos de OpenAPI. |
| E2E | Un recorrido pequeño y determinista de ingesta a consulta. |

Casos especialmente valiosos:

- Repetir una ingesta sin duplicar resultados.
- Fallar a mitad del batch y conservar accesible la última ejecución válida.
- Inventario desconocido: no recomendar como si fuera cero.
- Serie sin ventas: métricas y cobertura con significado explícito.
- Forecast insuficiente para el periodo requerido por la política.
- Varias ejecuciones históricas sin duplicar agregados en consultas.

Consideraría excesivo:

- Probar la misma fórmula en cuatro niveles.
- Exigir cobertura del 100 %.
- Ejecutar búsquedas de hiperparámetros en cada PR.
- Usar todo el dataset en CI.
- Fallar CI porque el candidato no supera al baseline.

La corrección del software y la superioridad estadística del modelo son validaciones diferentes. El backtest debe producir evidencia reproducible, no convertirse en un test frágil.

## 11. REPOSITORIO

**La organización propuesta es válida. No la reemplazaría por otra arquitectura de carpetas.**

Ajustaría solamente estas convenciones:

- `core` debe tener una responsabilidad concreta y pequeña; evitar convertirlo en un contenedor de utilidades.
- `pipelines` coordina etapas y estado de ejecución.
- `analytics` contiene transformaciones y contratos de consumo analítico.
- `forecasting` y `replenishment` concentran sus respectivas reglas.
- `artifacts` contiene resultados generados; los archivos grandes no deberían versionarse por defecto.
- `data/sample` contiene una muestra pequeña redistribuible, una vez aclarada su licencia.
- `bi` y `docs` guardan el informe y las explicaciones necesarias para entenderlo.

No añadiría carpetas preventivamente. La división de tests puede ajustarse cuando existan pruebas reales; algunos tests de datos serán unitarios y otros de integración.

## 12. DEVOPS

Mantendría toda la infraestructura propuesta.

| Elemento | Evaluación |
|---|---|
| Docker | Facilita reproducibilidad y entrega. |
| Compose | Suficiente para API, PostgreSQL y ejecución del batch. |
| GitHub Actions | Adecuado para validaciones y despliegue. |
| GHCR | Reutiliza una herramienta que ya dominas. |
| VPS Ubuntu | Suficiente con recursos y volumen acotados. |
| Nginx | Encaja con HTTPS y exposición de la API. |
| CI/CD | Aporta valor si el proceso es comprensible y recuperable. |

**Cambiaría tres cosas del planteamiento:**

1. **No desplegaría primero una aplicación que necesita una migración aún no aplicada.** La secuencia debe considerar compatibilidad entre esquema y aplicación. Una pequeña ventana de mantenimiento es aceptable; no necesitas diseñar despliegue sin interrupciones.

2. **Backup no equivale a recuperación.** Conviene comprobar una restauración y reconocer que volver a la imagen anterior no revierte automáticamente la base de datos.

3. **Separaría despliegue de ejecución analítica.** Publicar una nueva imagen no debería lanzar inevitablemente un entrenamiento completo.

Además del health check de la API, comprobaría la última ejecución correcta del batch y la antigüedad de los resultados. Logs y una tabla de ejecuciones bastan inicialmente.

En CI usaría PostgreSQL real para las pruebas relevantes y una muestra pequeña. Reservaría evaluaciones más costosas para ejecuciones deliberadas.

## 13. NUEVAS TECNOLOGÍAS

**Mantendría las tres, pero distribuiría el esfuerzo de forma desigual.**

| Novedad | Peso real |
|---|---|
| Forecasting | Principal dificultad conceptual. |
| Power BI | Principal herramienta nueva y aprendizaje de modelado/medidas. |
| uv | Incorporación pequeña al flujo de desarrollo. |

La advertencia es que la reposición también introduce conocimiento nuevo: cobertura, tiempos de suministro, incertidumbre y posición de inventario.

Por tanto, aunque incorpores pocas herramientas, el aprendizaje real incluye **forecasting, BI y fundamentos de inventario**. uv no debería convertirse en una línea de trabajo propia.

No añadiría otra tecnología para «aprovechar» que uv es pequeña.

## 14. SEÑAL PARA EMPLEO

Estas puntuaciones son **subjetivas**. Valoran las competencias que podría demostrar una versión terminada y bien explicada; no representan probabilidades de contratación.

| Perfil | Puntuación | Justificación |
|---|---:|---|
| Backend Python Junior | **8,5/10** | API, persistencia, procesos batch, testing y despliegue con lógica real. |
| Software Developer Junior | **8/10** | Límites modulares, reproducibilidad y decisiones técnicas defendibles. |
| Data Analyst / BI Junior | **8/10** | Buena combinación de SQL, modelo dimensional y análisis si las conclusiones están trabajadas. |
| Data Engineer Junior | **8/10** | Ingesta, calidad, transformaciones, trazabilidad e idempotencia. |
| Data Scientist Junior | **6,5/10** | Acredita un caso de forecasting, pero cubre parcialmente la amplitud estadística del perfil. |
| AI/Data Developer Junior | **8,5/10** | Integra procesamiento, modelos y reglas empresariales en software consumible. |

Para Java/Spring aporta señal general de ingeniería, pero poca evidencia nueva específica de Java. Tu segundo proyecto ya cumple esa función.

**No intentaría elevar todas las puntuaciones a la vez.** El centro más coherente es Python + Data Engineering + Analytics, con forecasting aplicado.

## 15. RIESGOS DEL PROYECTO

| Riesgo | Consecuencia | Cómo acotarlo |
|---|---|---|
| **1. Dataset inadecuado** | Puede carecer de historia útil, disponibilidad o permisos de redistribución. | Evaluar su aptitud antes de cerrar el diseño detallado. |
| **2. Inventario inexistente o poco fiable** | Recomendaciones que aparentan describir una realidad que no está en los datos. | Separar datos observados y escenarios simulados, identificándolos explícitamente. |
| **3. Forecasting engañoso** | Fuga temporal, demanda intermitente o ventas limitadas por stock pueden inflar resultados. | Backtest honesto, baseline y límites documentados. |
| **4. Alcance excesivo** | Terminar con varios subsistemas incompletos. | Priorizar un recorrido empresarial completo y acotado. |
| **5. Interpretación empresarial incorrecta** | Doble conteo, stock desactualizado o desconocimiento de pedidos pendientes generan decisiones erróneas. | Definiciones consistentes, fechas de referencia y recomendaciones explicables. |

El riesgo más importante no es elegir mal FastAPI o pandas: **es construir sobre datos que no permiten sostener las afirmaciones del producto.**

## 16. ALTERNATIVA

La variante que recomendaría es:

**DemandIQ como sistema de análisis de ventas y apoyo a reposición mediante escenarios explicables.**

Mantiene la arquitectura propuesta, pero delimita mejor qué puede demostrar:

- Analiza ventas reales.
- Compara previsiones con resultados observados.
- Aplica políticas de reposición sobre inventario real cuando exista.
- Utiliza escenarios explícitos cuando falten inventario o parámetros operativos.
- Expone recomendaciones y sus fundamentos mediante API y BI.

Por ejemplo, puede demostrar cómo cambia una recomendación al cambiar un supuesto de suministro, sin necesitar una nueva interfaz ni un sistema de gestión de proveedores.

Esta variante es especialmente útil si el dataset finalmente contiene ventas, pero no inventario. **No presentaría una simulación como ahorro real ni como reducción observada de roturas.**

No incorporaría inicialmente un simulador completo de inventario: basta con que las recomendaciones sean trazables y sus supuestos visibles.

## 17. VEREDICTO FINAL

**B) Seguir pero cambiando varios puntos.**

Mantendría arquitectura y stack. Los cambios principales serían:

- Delimitarlo como apoyo a decisiones de reposición.
- Distinguir ventas observadas de demanda.
- Dar prioridad a trazabilidad, reejecución segura y vigencia de resultados.
- Considerar la frecuencia de revisión y la posición de inventario al diseñar reposición.
- Acotar BI, testing y despliegue para que acompañen al flujo principal.
- Usar escenarios declarados cuando los datos no permitan recomendaciones basadas en inventario real.

**Es una buena tercera pieza de portfolio:** amplía tus competencias y aprovecha lo que ya sabes. Su calidad dependerá más de la coherencia entre datos, evaluación y decisiones que del número de funcionalidades.

Los diez puntos que has reservado permanecen abiertos; esta revisión no fija dataset, granularidad, horizonte, políticas, formato, KPIs, endpoints, modelos ni Definition of Done.
