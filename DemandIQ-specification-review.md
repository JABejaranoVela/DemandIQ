## 1. TU COMPRENSIÓN DE DEMANDIQ

DemandIQ convertirá ventas históricas reales de M5 en análisis, previsiones y propuestas explicables de reposición.  
La parte predictiva estimará **ventas observadas**, sin afirmar que recupera demanda perdida.  
Las recomendaciones combinarán esas previsiones con un escenario de inventario identificado y sus políticas.  
El sistema permitirá conocer qué se recomienda, por qué y con qué datos y supuestos.  
Un pipeline batch preparará los datos, evaluará baseline y candidato, y calculará resultados.  
FastAPI permitirá consultarlos sin ejecutar entrenamientos.  
Power BI permitirá analizar ventas, rendimiento predictivo y recomendaciones.  
Cada resultado será trazable hasta su ejecución y configuración.  
Los fallos no sustituirán los últimos resultados publicados correctamente.  
El objetivo es demostrar un recorrido de ingeniería y análisis completo, reproducible y acotado.

## 2. QUÉ ESTÁ YA CERRADO

- **Producto:** análisis de ventas, forecasting y apoyo a decisiones de reposición.
- **Finalidad:** portfolio orientado a Python backend, datos, BI y forecasting aplicado.
- **Dataset principal:** Walmart M5.
- **Objetivo predictivo:** ventas observadas, no demanda no restringida.
- **Inventario:** información externa o escenarios explícitos; nunca atribuida a Walmart.
- **Arquitectura general:** monolito modular con pipeline batch.
- **Separaciones:** batch/serving y forecasting/reposición; entrenamiento, evaluación y predicción conceptualmente distintos.
- **Persistencia conceptual:** RAW, CORE y ANALYTICS.
- **Stack:** el que has enumerado, incluido Python 3.13.
- **Experimento inicial:** un baseline y exactamente un candidato, comparados mediante evaluación temporal.
- **Éxito del proyecto:** no depende de que el candidato gane.
- **Resultados:** explicables, trazables y asociados a ejecuciones identificables.
- **Operación:** reingesta sin duplicación y conservación de la última ejecución válida ante fallos.
- **Consumo:** FastAPI y Power BI sobre resultados publicados.
- **Entrega:** Docker, CI/CD y API desplegada en VPS Ubuntu detrás de Nginx.
- **Repositorio:** único, organizado por responsabilidades, sin carpetas preventivas.
- **Exclusiones:** ERP, compras reales, multiempresa, frontend nuevo y tecnologías expresamente descartadas.

La **Definition of Done está aceptada como compromiso funcional**. Faltan concretar sus parámetros de aceptación, no reinventarla.

## 3. QUÉ SIGUE ABIERTO

| Bloque | Decisiones pendientes |
|---|---|
| **1. Alcance y DoD** | Delimitar las consultas, análisis y demostración mínimos que materializan la DoD. Comprobar su ajuste al tiempo disponible. |
| **2. Subconjunto y granularidad** | Tiendas, productos, agrupaciones, historia, frecuencia y selección reproducible. Tratamiento de series cortas e intermitentes. |
| **3. Fecha y horizonte** | Corte histórico, horizonte, frecuencia de predicción y relación con el periodo de protección. |
| **4. Entrada y calidad** | Archivos obligatorios, entrada del escenario, validaciones, ausencias, duplicados, correcciones y reingesta. |
| **5. Forecasting** | Evaluación temporal, métricas, baseline, candidato, features y series insuficientes. También qué forecast alimentará la reposición. |
| **6. Reposición** | Significado del stock, lead time, revisión, protección, entradas y compromisos incluidos, redondeo y casos sin recomendación. |
| **7. API y BI** | Preguntas prioritarias, KPIs, consultas, filtros y metadatos. Después, contratos concretos de consulta. |
| **8. Ejecución y fallos** | Inicio del batch, secuencia, publicación, fallos parciales, reejecución y criterio de vigencia. |
| **9. Demo y aceptación** | Presentación, exposición pública, Power BI, distribución de datos y artefactos, condiciones de M5 y evidencias de aceptación. |

**No falta un décimo bloque imprescindible.** Las cuestiones pendientes caben en los nueve existentes.

## 4. CONTRADICCIONES O AMBIGÜEDADES

**No detecto ninguna contradicción grave que obligue a cambiar el proyecto, el dataset o el stack.** Sí hay cinco ambigüedades que debemos resolver:

1. **Forecast utilizado para reponer.**  
   Ejecutar baseline y candidato no determina cuál produce la recomendación. Debemos establecer una regla explícita que no elija retrospectivamente usando el test final.

2. **Ejecución completa frente a producto sin recomendación.**  
   La DoD permite explicar que no se puede recomendar. Ese resultado empresarial puede ser válido y no debería confundirse automáticamente con un fallo técnico de toda la ejecución.

3. **Coherencia entre API y Power BI.**  
   Power BI en Import Mode puede conservar una publicación anterior mientras la API ya sirve otra. Debemos exigir coherencia dentro de cada publicación e identificarla; sincronía instantánea entre consumidores sería una exigencia adicional innecesaria.

4. **Vigencia sobre un dataset histórico.**  
   Hay que distinguir fecha histórica de referencia, momento de procesamiento y última publicación. Un resultado sobre 2016 no está desactualizado únicamente por no contener ventas de hoy.

5. **Resultados publicados frente a fuentes que cambian.**  
   Una nueva ingesta o corrección no debe modificar silenciosamente los datos que sustentan una publicación anterior. La coherencia prometida debe abarcar también las ventas utilizadas en comparaciones y métricas.

Son precisiones de comportamiento, no propuestas de nuevas funcionalidades.

## 5. BLOQUEADORES PARA EMPEZAR

### A) Deben resolverse antes del primer hito funcional

- **Datos iniciales:** archivos, subconjunto, granularidad y periodo exactos.
- **Acceso y uso:** verificar las condiciones aplicables al uso inicial de M5.
- **Contrato mínimo de ingesta:** identidad de los registros, validaciones esenciales, duplicados y tratamiento de una corrección.
- **Aceptación del primer recorrido:** qué resultado consultable demuestra que la ingesta y transformación funcionan correctamente.

Estas decisiones bastan para comenzar el hito de datos. **No hace falta cerrar toda la reposición antes de escribir la primera parte funcional.**

### B) Pueden resolverse durante el desarrollo, antes de su fase correspondiente

- Cortes de evaluación, horizonte, métricas y modelos: antes de implementar forecasting.
- Política operativa y forecast utilizado: antes de implementar reposición.
- Semántica completa de publicación: antes de exponer resultados analíticos como publicados.
- KPIs y contratos definitivos: antes de completar API y BI.
- Frecuencias automáticas y vigencia: antes de automatizar la operación.
- Forma de compartir Power BI y permisos de distribución: antes de publicar los artefactos afectados.
- Organización exacta de módulos, tablas, índices y pruebas: conforme se concreten las responsabilidades.

**Poder resolverlas durante el desarrollo no significa permitir decisiones implícitas.** Cada una debe quedar acordada antes de implementar el comportamiento que condiciona.

## 6. ORDEN DE DECISIONES

Resolvería los bloques en este orden:

1. **Alcance y DoD:** confirmar el límite del trabajo.
2. **Demo, publicación y aceptación:** comprobar pronto permisos y requisitos mínimos de presentación; los detalles visuales pueden esperar.
3. **Subconjunto y granularidad:** fijar con qué datos trabajamos.
4. **Fecha de referencia y horizonte:** establecer el marco temporal.
5. **Política de reposición:** comprobar que ese marco permite cubrir sus necesidades.
6. **Contrato de entrada y calidad:** concretar ventas y parámetros operativos ya entendidos.
7. **Experimento de forecasting:** definir evaluación y después baseline/candidato.
8. **Resultados para API y BI:** elegir cómo consultar y explicar los resultados acordados.
9. **Ejecución y fallos:** cerrar la coordinación y publicación del recorrido completo.

Los bloques **3 y 6 de tu numeración —horizonte y reposición— deben comprobarse conjuntamente**. No cerraría un horizonte incompatible con el periodo de protección.

Este orden de decisiones no obliga a esperar hasta el último bloque para comenzar el primer hito.

## 7. PLAN GENERAL DE CONSTRUCCIÓN

| Fase | Resultado esperado |
|---|---|
| **Fase 0 — Especificación mínima** | Resolver los bloqueadores del primer hito y registrar las decisiones aceptadas. |
| **Fase 1 — Datos hasta consulta** | Preparar, ingerir, validar y transformar un subconjunto; consultar ventas y trazabilidad mediante API. |
| **Fase 2 — Evaluación predictiva** | Comparación temporal reproducible del baseline y único candidato. |
| **Fase 3 — Forecast y reposición** | Predicciones asociadas a una fecha y recomendaciones explicadas sobre un escenario. |
| **Fase 4 — Publicación coherente** | Resultados completos consultables, conservación de la publicación anterior y tratamiento de fallos. |
| **Fase 5 — Business Intelligence** | Informe que analice ventas, evaluación y recomendaciones con sus metadatos. |
| **Fase 6 — Entrega y aceptación** | Despliegue, demostración reproducible y comprobación de la DoD completa. |

Testing, documentación, Docker y CI acompañarán las fases desde el primer recorrido. No se dejarán como una tarea final acumulada. El despliegue y su automatización se completarán cuando exista un resultado estable que entregar.

## 8. PRIMER HITO IMPLEMENTABLE

**Un subconjunto de M5 ingerido de forma reproducible, validado y consultable mediante FastAPI.**

El recorrido sería:

**M5 seleccionado → carga identificada → validación → transformación → persistencia → consulta de ventas y trazabilidad.**

Se consideraría logrado cuando:

- La selección pueda repetirse y producir el mismo conjunto.
- Los totales transformados coincidan con el origen seleccionado.
- Reingerir los mismos datos no duplique ventas.
- Los errores de entrada tengan un resultado explícito.
- La consulta permita comprobar ventas y procedencia.
- Un E2E pequeño verifique el recorrido.

Todavía no sería la publicación analítica completa de V1. Sería una primera entrega funcional que valida la base sobre la que se construirán forecasting y reposición.

## 9. CRITERIO DE SIMPLICIDAD

Vigilaré especialmente:

- **Datos:** no cargar M5 completo por prestigio.
- **Modelos:** mantener un baseline y un candidato, sin búsqueda extensa ni modelos por producto injustificados.
- **Reposición:** evitar convertir escenarios en gestión de compras o simulación completa.
- **Publicación:** resolver consistencia sin construir un orquestador genérico.
- **API:** consultas necesarias, sin CRUD para cada entidad.
- **BI:** pocas preguntas bien contestadas, sin duplicar reglas empresariales.
- **Persistencia:** que cada capa tenga una responsabilidad; evitar copias sin propósito.
- **Estructura:** crear módulos por necesidad real, no por una plantilla arquitectónica.
- **Pruebas:** comprobar riesgos y reglas, sin repetir la misma validación en todos los niveles.
- **Infraestructura:** mantener el stack acordado salvo bloqueo demostrado.

## 10. CONFIRMACIÓN FINAL

Los únicos bloqueadores para comenzar el primer hito son:

1. Fijar archivos, subconjunto, granularidad y periodo de M5.
2. Verificar las condiciones aplicables a su acceso y uso inicial.
3. Cerrar el contrato mínimo de ingesta y su comportamiento ante duplicados, errores y correcciones.
4. Acordar la consulta mínima y los criterios de aceptación del recorrido de datos.

READY TO IMPLEMENT AFTER PENDING DECISIONS
