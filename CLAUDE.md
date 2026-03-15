# Especificación de producto — Prediction Markets Research Workbench (PMRW)

## 1. Resumen ejecutivo

**Nombre provisional:** PMRW — Prediction Markets Research Workbench
**Tipo de producto:** plataforma modular para lectura de mercados, paper trading, modelado probabilístico, backtesting y alertas
**Fase 1:** solo investigación, simulación, valoración y paper trading
**No objetivo inicial:** ejecución con dinero real, market making, arbitraje multi-venue de baja latencia, custodia on-chain, wallets, smart contracts, ni sistemas HFT

La idea es construir una plataforma **feasible** para ser implementada con Codex + GPT-5.4 High o Claude Code + Opus 4.6, con una arquitectura clara, modular, orientada al dominio, muy testeable y con foco explícito en **TDD + alta cobertura**.

El producto debe permitir:

1. **Leer mercados** desde una o más fuentes.
2. **Normalizar** datos de mercados, precios, snapshots y eventos.
3. **Calcular probabilidades implícitas** y señales simples de edge.
4. **Mantener modelos propios** de probabilidad/base rates/Bayes simples.
5. **Simular trades** mediante un paper broker con costos, slippage y reglas de sizing.
6. **Backtestear** estrategias sobre datos históricos.
7. **Emitir alertas** cuando existan diferencias relevantes entre probabilidad del modelo y precio de mercado.
8. **Auditar y explicar** por qué el sistema generó una decisión.

El objetivo no es “ganar dinero automáticamente” en la Fase 1, sino crear un **laboratorio de decisión probabilística** que luego pueda evolucionar hacia ejecución real.

---

## 2. Principios de diseño

### 2.1 Principios de producto

* **Primero investigación, después automatización.**
* **Primero simulación, después riesgo real.**
* **Primero explicabilidad, después sofisticación.**
* **Primero integridad de datos, después features exóticas.**
* **Primero arquitectura extensible, después optimización prematura.**

### 2.2 Principios de ingeniería

* SOLID
* Clean Architecture / Hexagonal Architecture
* Domain-Driven Design liviano
* Inmutabilidad por defecto donde tenga sentido
* Contratos explícitos entre capas
* Testabilidad como requisito de diseño, no como agregado
* Trazabilidad completa de decisiones
* Separación estricta entre dominio, infraestructura y presentación

### 2.3 Principios de riesgo

* Sin órdenes reales en Fase 1
* Sin asumir que los datos del proveedor son correctos
* Toda métrica calculada debe poder trazarse a inputs concretos
* Todo modelo debe exponer incertidumbre, no solo valor puntual
* Toda estrategia debe declarar supuestos, rango de validez y failure modes

---

## 3. Problema que resuelve

La mayoría de los traders retail de prediction markets operan con una mezcla de intuición, narrativa y noticias, sin infraestructura para:

* comparar precio de mercado vs probabilidad propia,
* registrar hipótesis,
* medir expected value,
* simular sizing,
* backtestear consistentemente,
* y aprender del error.

PMRW resuelve ese problema ofreciendo una plataforma donde el usuario puede pasar de:

**leer mercados -> formular hipótesis -> cuantificar edge -> simular trades -> evaluar performance -> mejorar el modelo**

---

## 4. Usuario objetivo

### Usuario principal

Analista/trader técnico individual con interés en prediction markets que quiere trabajar con método cuantitativo ligero.

### Usuario secundario

Estudiante de data science, finance o econometría que quiere usar prediction markets como laboratorio aplicado de probabilidad, decisión y backtesting.

### Usuario futuro

Pequeño equipo de research que quiera extender el sistema a más fuentes, estrategias y eventualmente ejecución real.

---

## 5. Propuesta de valor

### Lo que entrega la Fase 1

* Un **workspace analítico serio** para prediction markets.
* Una **fuente única de verdad** para mercados, precios, señales y paper trades.
* Un **motor de evaluación** de edge sencillo y explicable.
* Un **paper broker** con reglas reproducibles.
* Un **backtester confiable** con fuerte cobertura de tests.

### Lo que no promete

* Rentabilidad garantizada
* Alpha mágico
* Automatización total de juicio
* Arbitraje profesional
* Modelos fundacionales complejos desde el inicio

---

## 6. Alcance funcional

## 6.1 Fase 1 — MVP serio y feasible

### Módulos incluidos

1. **Market ingestion**

   * Lectura de mercados activos e históricos desde un proveedor inicial.
   * Pull programado de snapshots.
   * Persistencia de datos crudos y normalizados.

2. **Canonical domain model**

   * Event
   * Market
   * Outcome
   * PriceSnapshot
   * OrderBookSnapshot opcional si la fuente lo soporta
   * ModelEstimate
   * Signal
   * PaperOrder
   * PaperFill
   * Position
   * Portfolio
   * StrategyRun

3. **Research workspace**

   * Ver mercados.
   * Ver historial.
   * Registrar tags, notas y supuestos.
   * Asociar mercados a tesis/hypotheses.

4. **Probability engine**

   * Implied probability
   * Normalización básica
   * Base-rate models
   * Bayesian updater simple
   * Confidence interval helpers

5. **Signal engine**

   * EV gap
   * threshold alerts
   * rule-based scoring
   * ranking de oportunidades

6. **Paper trading engine**

   * Simular órdenes de compra/venta
   * Simular slippage configurable
   * Simular fees
   * Position sizing por fixed stake o fractional Kelly conservador

7. **Backtesting**

   * Replay de snapshots históricos
   * Evaluación de señales vs resultados posteriores
   * Métricas de estrategia

8. **Observability & auditability**

   * Logs estructurados
   * Event trail de decisiones
   * Explanations por señal y trade

9. **API + UI básica**

   * API backend limpia
   * UI web ligera enfocada en research y paper portfolio

### Fuera de alcance MVP

* Ejecución real
* Multi-exchange arbitrage en vivo
* Enrutamiento de órdenes
* Latencia ultra baja
* ML complejo en producción
* Modelos LLM como dependencia core del sistema
* Optimización combinatoria avanzada
* Sistemas multi-tenant completos

---

## 7. Roadmap de fases

## Fase 1 — Foundation / Research / Paper Trading

Objetivo: una plataforma sólida para leer, modelar, simular y evaluar.

## Fase 2 — Strategy Lab

* Más fuentes de datos
* Mejoras de backtesting
* Framework de estrategias enchufables
* Risk dashboards
* Calibración estadística más rica
* Alertas avanzadas

## Fase 3 — Assisted Execution

* Preparación para live trading
* Motor de órdenes desacoplado
* Approval flow manual
* Validaciones de riesgo pre-trade

## Fase 4 — Selective Automation

* Ejecución real con feature flags
* Límite estricto de riesgo
* Kill switch
* Post-trade reconciliation

---

## 8. Arquitectura propuesta

## 8.1 Estilo arquitectónico

**Hexagonal / Ports and Adapters** con capas limpias.

### Capas

1. **Domain**

   * Entidades, value objects, invariantes, servicios de dominio puros

2. **Application**

   * Casos de uso / orchestration
   * Commands / queries
   * DTOs internos

3. **Infrastructure**

   * HTTP clients
   * repositorios
   * persistencia
   * scheduler
   * cache
   * adapters externos

4. **Interface**

   * REST API
   * CLI opcional
   * frontend web

5. **Cross-cutting**

   * logging
   * config
   * metrics
   * auth
   * feature flags

---

## 8.2 Arquitectura lógica

```text
[ External Market APIs ]
          |
          v
[ Ingestion Adapters ] ---> [ Raw Storage ]
          |
          v
[ Normalization Layer ] ---> [ Canonical DB ]
          |
          +--> [ Probability Engine ]
          |
          +--> [ Signal Engine ]
          |
          +--> [ Paper Broker ]
          |
          +--> [ Backtesting Engine ]
          |
          v
[ Application Services / Use Cases ]
          |
     +----+----+
     |         |
     v         v
 [ REST API ] [ CLI ]
     |
     v
 [ Web UI ]
```

---

## 8.3 Decisiones tecnológicas recomendadas

### Backend

* **Python 3.12+**
* **FastAPI** para API
* **Pydantic v2** para contratos de datos
* **SQLAlchemy 2.0** para persistencia
* **PostgreSQL** como base principal
* **Alembic** para migraciones
* **httpx** para clientes HTTP
* **Tenacity** para retries controlados
* **structlog** o logging estándar estructurado

### Background jobs

Opción simple y suficiente para MVP:

* scheduler liviano interno o APScheduler

Opción si se quiere mayor robustez luego:

* Celery / Dramatiq / RQ

### Frontend

* **Next.js** o **React + Vite**
* TypeScript
* TanStack Query
* tablas y gráficos simples

### Testing

* **pytest**
* **pytest-cov**
* **hypothesis** para property-based testing
* **pytest-asyncio**
* **factory_boy** o builders manuales
* **respx** o similar para mocking HTTP
* **testcontainers** para tests de integración con PostgreSQL

### Dev tooling

* ruff
* black
* mypy o pyright
* pre-commit
* Makefile o task runner
* Docker Compose para entorno local

---

## 9. Diseño del dominio

## 9.1 Bounded contexts

### A. Market Data Context

Responsable de eventos, mercados, outcomes, snapshots y normalización.

### B. Modeling Context

Responsable de probabilidades propias, supuestos, calibraciones y estimaciones.

### C. Signal Context

Responsable de transformar diferencias entre mercado y modelo en oportunidades evaluables.

### D. Paper Trading Context

Responsable de órdenes simuladas, fills, posiciones y portfolio.

### E. Backtesting Context

Responsable de replay histórico, evaluación y métricas.

### F. Research Context

Responsable de notas, tags, watchlists, hipótesis y explicaciones.

---

## 9.2 Entidades principales

### Event

Representa el hecho subyacente.

Campos sugeridos:

* event_id
* source_event_id
* title
* description
* category
* status
* open_time
* close_time
* resolve_time
* metadata

### Market

Representa el instrumento transable asociado a un evento.

Campos:

* market_id
* event_id
* source_market_id
* market_type
* venue
* quote_currency
* status
* rules_text
* resolution_source
* metadata

### Outcome

Representa YES / NO u otros outcomes si luego se extiende.

Campos:

* outcome_id
* market_id
* name
* side

### PriceSnapshot

Representa un snapshot temporal del estado observable del mercado.

Campos:

* snapshot_id
* market_id
* captured_at
* best_bid
* best_ask
* mid_price
* last_price
* volume
* liquidity_hint
* raw_payload_ref

### ModelEstimate

Representa la probabilidad propia calculada por un modelo.

Campos:

* estimate_id
* market_id
* model_name
* version
* estimated_probability
* lower_bound
* upper_bound
* generated_at
* inputs_hash
* explanation

### Signal

Representa una oportunidad detectada.

Campos:

* signal_id
* market_id
* estimate_id
* signal_type
* market_probability
* model_probability
* edge_bps
* expected_value
* confidence_score
* rationale
* generated_at

### PaperOrder

Representa una orden simulada.

Campos:

* paper_order_id
* portfolio_id
* market_id
* side
* quantity
* limit_price
* submitted_at
* status
* source_signal_id nullable

### PaperFill

Representa una ejecución simulada.

Campos:

* paper_fill_id
* paper_order_id
* fill_price
* fill_quantity
* fee_amount
* slippage_amount
* filled_at

### Position

Representa la posición agregada por mercado.

Campos:

* position_id
* portfolio_id
* market_id
* net_quantity
* avg_cost
* realized_pnl
* unrealized_pnl
* marked_at

### StrategyRun

Representa una corrida de estrategia/backtest.

Campos:

* strategy_run_id
* strategy_name
* version
* config
* started_at
* ended_at
* status
* summary_metrics

---

## 9.3 Value objects sugeridos

* Probability
* Price
* Money
* Quantity
* Percentage
* TimeRange
* MarketProbabilitySpread
* ConfidenceInterval
* SlippageModel
* FeeModel

Estos value objects deben encapsular validaciones e invariantes.

Ejemplo:

* Probability debe vivir en [0,1]
* Price no puede ser negativa
* Quantity no puede ser NaN
* ConfidenceInterval requiere lower <= upper

---

## 10. Casos de uso principales

## 10.1 Ingestar mercados

**Actor:** scheduler o usuario

**Flujo:**

1. Invocar adapter del proveedor.
2. Descargar payload crudo.
3. Validar esquema externo.
4. Persistir raw payload.
5. Transformar a canonical model.
6. Upsert de entidades.
7. Registrar resultado y métricas.

## 10.2 Generar estimación de probabilidad

1. Seleccionar mercado.
2. Recuperar features relevantes.
3. Ejecutar modelo configurado.
4. Generar `ModelEstimate`.
5. Persistir estimate + explicación.

## 10.3 Detectar señal

1. Recuperar precio observable actual.
2. Recuperar estimación más reciente.
3. Calcular edge y EV.
4. Aplicar thresholds.
5. Emitir `Signal` si corresponde.

## 10.4 Simular orden

1. Usuario o estrategia envía intención de compra/venta.
2. Risk policy valida.
3. Paper broker calcula fill estimado.
4. Persiste orden, fill y actualiza posición.
5. Registra explicación de sizing y costos.

## 10.5 Ejecutar backtest

1. Elegir estrategia + intervalo.
2. Reproducir snapshots en orden temporal.
3. Ejecutar señales.
4. Ejecutar broker simulado.
5. Calcular métricas.
6. Persistir `StrategyRun`.

---

## 11. Modelado probabilístico inicial

El objetivo del MVP no es tener un modelo brillante, sino un conjunto de modelos simples, testeables y comparables.

## 11.1 Modelo A — Implied probability baseline

Toma precio observable y lo usa como baseline.

Uso:

* benchmark
* sanity check
* comparación con modelos propios

## 11.2 Modelo B — Base-rate model

Estimación basada en frecuencias históricas del tipo de evento.

Ejemplos:

* tipo de mercado
* categoría
* condiciones análogas predefinidas

## 11.3 Modelo C — Bayesian updater simple

* prior desde base rates
* evidencia definida explícitamente
* likelihoods configurables
* posterior calculado con trazabilidad

## 11.4 Modelo D — Manual analyst override

Permite al usuario registrar una probabilidad subjetiva propia con explicación.

Esto es útil porque en research humano muchas veces la hipótesis nace antes que el modelo automatizado.

---

## 12. Signal engine inicial

### Señales mínimas

1. **Probability gap signal**

   * `model_probability - market_probability`

2. **Expected value signal**

   * EV aproximado dado payoff simple y costo estimado

3. **Threshold signal**

   * alertar cuando el edge supera X bps

4. **Confidence-weighted signal**

   * reduce score si la incertidumbre del modelo es alta

### Requisitos

* Ninguna señal puede depender directamente de la UI
* Deben ser funciones puras o casi puras, fáciles de testear
* Toda señal debe producir una explicación serializable

---

## 13. Paper broker

## 13.1 Objetivo

Simular comportamiento de ejecución con suficiente realismo para no engañar al usuario, sin caer en complejidad de exchange real.

## 13.2 Reglas mínimas

* soporte buy/sell
* fill al mejor precio observable disponible según política
* slippage configurable
* fees configurables
* partial fills opcionales en fase posterior
* validación de límites de riesgo

## 13.3 Modelos de ejecución

### Modelo 1 — Mid-price naive

Útil para tests y baseline, no realista.

### Modelo 2 — Best bid/ask realistic-lite

Usa mejor ask para comprar y mejor bid para vender, más slippage configurable.

### Modelo 3 — Order book aware

Fase posterior, si se dispone de profundidad suficiente.

## 13.4 Position sizing

Soportar al menos:

* fixed unit size
* fixed dollar risk
* fractional Kelly capped

**Regla importante:** Kelly nunca se usa full por defecto. Debe estar capado y acompañado por warnings.

---

## 14. Backtesting engine

## 14.1 Requisitos funcionales

* replay temporal determinístico
* sin lookahead bias
* separación entre training/calibration y evaluation
* métricas reproducibles
* configuración serializable

## 14.2 Métricas mínimas

* total return paper
* hit rate
* average edge captured
* max drawdown
* Sharpe simplificado si aplica
* Brier score para calidad probabilística
* calibration curve outputs
* average holding time
* turnover

## 14.3 Riesgos metodológicos a explicitar

* selection bias
* survivorship bias
* lookahead bias
* data snooping
* overfitting de thresholds

---

## 15. API de aplicación

## 15.1 Endpoints MVP sugeridos

### Markets

* `GET /markets`
* `GET /markets/{market_id}`
* `GET /markets/{market_id}/snapshots`

### Estimates

* `POST /markets/{market_id}/estimates/run`
* `GET /markets/{market_id}/estimates`

### Signals

* `POST /signals/run`
* `GET /signals`

### Paper trading

* `POST /paper-orders`
* `GET /paper-orders`
* `GET /positions`
* `GET /portfolio`

### Backtesting

* `POST /backtests/run`
* `GET /backtests/{strategy_run_id}`

### Research

* `POST /watchlists`
* `POST /notes`
* `GET /research/markets/{market_id}`

---

## 16. UI MVP

## Pantallas mínimas

1. **Market Explorer**

   * lista de mercados
   * filtros
   * precios actuales
   * edge estimado

2. **Market Detail**

   * historial de precios
   * estimaciones del modelo
   * señales emitidas
   * notas del usuario

3. **Paper Portfolio**

   * posiciones
   * PnL paper
   * historial de órdenes/fills

4. **Backtest Runs**

   * lista de corridas
   * métricas
   * gráficos básicos

5. **Research Notes**

   * watchlists
   * tags
   * hipótesis por mercado

### Principios UX

* UI explicativa antes que “bonita”
* mostrar inputs y supuestos
* evitar dashboards recargados
* facilitar trazabilidad de cada número

---

## 17. Diseño de datos y persistencia

## 17.1 Estrategia de almacenamiento

Separar:

1. **Raw data store**

   * payloads externos sin alterar
   * útil para auditoría y replay

2. **Canonical relational store**

   * entidades normalizadas
   * consultas operativas

## 17.2 Tablas mínimas

* raw_market_payloads
* events
* markets
* outcomes
* price_snapshots
* model_estimates
* signals
* portfolios
* paper_orders
* paper_fills
* positions
* strategy_runs
* research_notes
* watchlists

## 17.3 Requisitos de persistencia

* timestamps consistentes UTC
* constraints explícitos
* índices por market_id + timestamp
* historial append-only para snapshots y estimates

---

## 18. Seguridad y confiabilidad

Aunque el MVP no ejecute dinero real, debe diseñarse con disciplina financiera.

### Requisitos

* manejo seguro de API keys aunque sean solo de lectura
* configuración por entorno
* rate limiting sobre API propia si aplica
* retries controlados y circuit-breaking básico para proveedores externos
* validación fuerte de inputs
* logs sin datos sensibles
* idempotencia en jobs críticos de ingestión

---

## 19. Observabilidad

### Logs

Cada caso de uso debe producir logs estructurados con:

* correlation_id
* use_case
* market_id si aplica
* provider
* result
* duration_ms

### Métricas

* mercados ingeridos por corrida
* latency de proveedor externo
* cantidad de señales generadas
* backtests ejecutados
* error rate por adapter

### Audit trail

Toda señal y toda orden paper deben poder explicar:

* qué datos usaron
* qué modelo usaron
* qué thresholds aplicaron
* qué sizing rule aplicaron

---

## 20. Estrategia de testing

Este es el corazón del proyecto.

Además, la suite de tests y parte de la documentación técnica deben funcionar como una **capa pedagógica semi-académica**: no solo verificar que el sistema funciona, sino también explicar con precisión técnica por qué ciertas reglas, fórmulas, métricas y supuestos son correctos o razonables dentro del stack financiero-probabilístico del producto.

## 20.1 Filosofía

En aplicaciones financieras, los tests no solo evitan bugs: **enseñan el dominio**.
La suite debe funcionar como documentación ejecutable.

Esto implica que, cuando sea útil, los tests y la documentación asociada deben incluir:

* explicación conceptual del objetivo financiero o probabilístico de la pieza testeada,
* explicación técnica del mecanismo matemático o estadístico subyacente,
* supuestos de validez, limitaciones y failure modes,
* ejemplos numéricos pequeños y reproducibles,
* fórmulas en LaTeX cuando aporten claridad real.

El tono deseado no es el de un paper formal, sino **apenas académico**: claro, técnico, sobrio y pedagógico.

## 20.2 Objetivos de cobertura

* **Dominio:** 95%+
* **Aplicación:** 90%+
* **Infraestructura crítica:** alta cobertura con integración selectiva
* **Cobertura total útil:** 85%+ sin perseguir coverage artificial

No perseguir 100% ciego. Perseguir alta cobertura donde hay reglas, dinero simulado, probabilidades, sizing, PnL y backtesting.

## 20.3 Pirámide de tests

### A. Unit tests — base del sistema

Probar:

* value objects
* invariantes
* servicios de dominio
* cálculos de probabilidad
* EV
* Kelly fraccional
* fees
* slippage
* PnL
* scoring de señales

Deben ser rápidos, determinísticos y numerosos.

### B. Property-based tests

Usar Hypothesis para:

* probabilidades siempre en [0,1]
* precios no negativos
* PnL consistente bajo transformaciones esperadas
* monotonicidad de ciertas funciones
* invariantes del portfolio
* ausencia de estados imposibles

### C. Integration tests

Probar:

* repositorios contra PostgreSQL real en testcontainers
* adapters HTTP contra mocks realistas
* migraciones
* casos de uso completos con persistencia

### D. Contract tests

Para adapters externos:

* mapping del payload externo a canonical model
* tolerancia a campos faltantes
* manejo de cambios de esquema

### E. End-to-end tests

Pocos pero críticos:

* ingestar -> normalizar -> estimar -> señal -> orden paper -> posición
* backtest completo pequeño

---

## 20.4 Estilo de tests y documentación pedagógica

### Requisito transversal

Para módulos críticos, cada conjunto de tests debe responder explícitamente, idealmente en docstrings, comentarios estructurados o archivos de apoyo en `docs/domain/` o `docs/math/`, a estas preguntas:

1. **Qué representa esta pieza dentro del sistema financiero.**
2. **Qué propiedad matemática, estadística o contable debe cumplirse.**
3. **Qué fórmula o identidad justifica el comportamiento esperado.**
4. **Qué puede salir mal si la implementación viola esa propiedad.**

### Casos donde debe haber explicación técnica reforzada

Especialmente en:

* implied probability
* expected value
* break-even probability
* Bayesian updating
* Brier score
* calibration metrics
* Kelly sizing y fractional Kelly
* PnL realizado/no realizado
* fee models
* slippage models
* portfolio aggregation
* backtesting sin lookahead bias
* intervalos de confianza y medidas de incertidumbre

### Nivel de formalismo esperado

No hace falta demostrar teoremas de forma completamente rigurosa, pero sí conviene incluir:

* derivaciones cortas,
* intuición matemática,
* interpretación económica/financiera,
* ejemplos simples con números,
* notas sobre unidades y escalas.

### Formato sugerido

1. **Docstring técnico breve** en el módulo o función.
2. **Test nombrado pedagógicamente** que exprese la propiedad.
3. **Comentario o nota matemática** cuando la lógica no sea obvia.
4. **Documento de apoyo** en `docs/math/` o `docs/domain/` para piezas más densas.

### Ejemplos de contenido esperado

#### Expected Value

Explicar que, para un contrato binario simple, el valor esperado puede escribirse como:

$$
EV = p \cdot W - (1-p) \cdot L
$$

Y que, si el contrato paga 1 al resolver YES y el costo efectivo de entrada es `c`, entonces una forma simple del retorno esperado por unidad puede escribirse como:

$$
EV = p \cdot (1-c) + (1-p) \cdot (-c) = p - c
$$

cuando se ignoran fees adicionales y se trabaja en unidades normalizadas. Los tests deben dejar claro bajo qué supuestos esta simplificación es válida y cuándo deja de serlo.

#### Bayesian updating

Explicar la fórmula:

$$
P(H \mid E) = \frac{P(E \mid H)P(H)}{P(E)}
$$

Y aclarar qué representa cada término en el contexto del producto: prior, likelihood, evidencia y posterior. Los tests deben mostrar al menos un ejemplo numérico donde nueva evidencia incremente la probabilidad posterior y otro donde la reduzca.

#### Kelly Criterion

Explicar que el criterio de Kelly maximiza el crecimiento logarítmico esperado del capital bajo supuestos ideales, y que en práctica se usa una versión fraccional por error de estimación. Debe incluirse la fórmula correspondiente al caso implementado y una nota explícita sobre por qué **full Kelly no será el default**.

#### Brier score

Explicar que para eventos binarios el Brier score es:

$$
BS = \frac{1}{N}\sum_{i=1}^{N}(f_i - o_i)^2
$$

Y que menor es mejor. Los tests deben verificar casos canónicos: predicción perfecta, totalmente errada e intermedia.

#### Lookahead bias

La documentación de backtesting debe explicar en lenguaje técnico simple por qué usar información futura contamina la evaluación y produce performance ficticia. Idealmente incluir una línea temporal pequeña en texto o markdown.

## 20.5 Estrategia TDD

### Regla

Cada feature se construye siguiendo:

1. escribir test de comportamiento
2. ver fallo
3. implementar mínimo necesario
4. refactorizar
5. ampliar cobertura con casos borde

### Orden sugerido de implementación por TDD

1. value objects
2. entidades de dominio
3. cálculos puros
4. políticas de riesgo/sizing
5. casos de uso
6. repositorios
7. adapters externos
8. API
9. UI

### Ejemplos de tests pedagógicos

#### Probability

* rechaza valores < 0 o > 1
* acepta 0, 1 y puntos intermedios

#### EV calculation

* EV positivo cuando model_probability > market_break_even ajustado por fees
* EV cae cuando fees suben

#### Kelly

* no devuelve tamaño negativo para edge no positivo
* respeta caps
* reduce tamaño si aumenta incertidumbre

#### Paper broker

* buy usa ask o política configurada
* sell usa bid o política configurada
* fees se descuentan correctamente
* no permite órdenes inválidas

#### Backtester

* no usa snapshots futuros
* reproduce orden temporal exacto
* mismo input produce mismo output

---

## 20.6 Convenciones de documentación técnica asociada a tests

### Estructura sugerida

```text
docs/
  domain/
    market_data.md
    paper_trading.md
    backtesting.md
  math/
    implied_probability.md
    expected_value.md
    bayes.md
    kelly.md
    brier_score.md
    pnl_and_mark_to_market.md
```

### Reglas

* Cada documento debe ser corto, claro y acumulativo.
* Debe enlazar conceptos del dominio con su implementación en código.
* Debe incluir fórmulas en LaTeX solo cuando agreguen precisión.
* Debe evitar grandilocuencia académica innecesaria.
* Debe dejar claro qué se implementa exactamente y qué se deja fuera.

### Requisito de trazabilidad

Cuando una parte del sistema implemente una fórmula o convención financiera específica, debe existir al menos una de estas dos cosas:

1. un test que exprese la propiedad matemática relevante, o
2. un documento técnico corto que explique la convención elegida y sus supuestos.

Idealmente ambas.

## 20.7 Ejemplos de carpetas de tests

```text
tests/
  unit/
    domain/
      test_probability.py
      test_price.py
      test_ev.py
      test_kelly.py
      test_signal_scoring.py
      test_position.py
      test_portfolio.py
    application/
      test_run_estimate_use_case.py
      test_generate_signal_use_case.py
      test_submit_paper_order_use_case.py
      test_run_backtest_use_case.py
  property/
    test_probability_properties.py
    test_portfolio_properties.py
    test_pricing_properties.py
  integration/
    persistence/
      test_market_repository.py
      test_estimate_repository.py
    providers/
      test_provider_adapter_mapping.py
    api/
      test_markets_api.py
      test_paper_orders_api.py
  e2e/
    test_ingest_to_paper_trade_flow.py
    test_backtest_flow.py
```

---

## 21. Estructura de repositorio sugerida

```text
pmrw/
  apps/
    api/
    web/
  packages/
    domain/
    application/
    infrastructure/
    contracts/
    testkit/
  migrations/
  scripts/
  tests/
  docs/
    adr/
    architecture/
    api/
    domain/
  docker/
  pyproject.toml
  Makefile
  docker-compose.yml
```

Si se prefiere un solo backend package para empezar, también es válido:

```text
src/pmrw/
  domain/
  application/
  infrastructure/
  interface/
  config/
  observability/
```

Para el MVP, esta segunda opción puede ser más simple.

---

## 22. Interfaces / ports clave

### Domain/Application ports

* `MarketRepository`
* `PriceSnapshotRepository`
* `ModelEstimateRepository`
* `SignalRepository`
* `PortfolioRepository`
* `PaperOrderRepository`
* `StrategyRunRepository`
* `ExternalMarketDataProvider`
* `Clock`
* `UnitOfWork`
* `EventBus` opcional

Esto permite testear con fakes antes de usar infraestructura real.

---

## 23. ADRs iniciales sugeridos

### ADR-001: Python + FastAPI + PostgreSQL

Motivo: velocidad de implementación, ecosistema científico, buena testabilidad.

### ADR-002: Arquitectura hexagonal

Motivo: desacoplar dominio de proveedores y UI.

### ADR-003: No live trading en MVP

Motivo: reducir riesgo y complejidad.

### ADR-004: Paper broker explainable antes que realista-extremo

Motivo: aprender primero, sofisticar luego.

### ADR-005: TDD obligatorio para dominio y aplicación

Motivo: reducir defectos y mejorar comprensión del negocio.

---

## 24. Riesgos del proyecto

### Riesgo 1 — Scope creep

Mitigación: no tocar ejecución real en MVP.

### Riesgo 2 — Sobreingeniería

Mitigación: hexagonal liviana, no microservicios.

### Riesgo 3 — Falsa confianza por paper trading

Mitigación: simular fees/slippage y mostrar advertencias.

### Riesgo 4 — Dependencia excesiva de un proveedor

Mitigación: adapters con ports y canonical model.

### Riesgo 5 — Modelos malos con apariencia sofisticada

Mitigación: benchmarks simples, calibration metrics y backtesting honesto.

---

## 25. Criterios de aceptación del MVP

El MVP se considera exitoso si puede:

1. Ingestar mercados y snapshots desde al menos una fuente.
2. Persistir datos crudos y normalizados.
3. Mostrar mercados y detalle histórico en UI.
4. Ejecutar al menos dos modelos simples de probabilidad.
5. Generar señales explicables.
6. Simular órdenes y portfolio paper.
7. Ejecutar un backtest reproducible.
8. Mantener cobertura alta en módulos críticos.
9. Correr localmente con un solo comando o pocos pasos claros.
10. Soportar extensión futura sin reescritura del dominio.

---

## 26. Plan de implementación sugerido

## Sprint 0 — Setup

* repo
* tooling
* CI
* lint/typecheck/test
* docker compose
* estructura base

## Sprint 1 — Domain core

* value objects
* entidades básicas
* tests de dominio

## Sprint 2 — Persistence + ingestion

* repositorios
* migraciones
* primer provider adapter
* raw + canonical persistence

## Sprint 3 — Probability + signals

* implied probability
* base-rate model
* Bayesian updater simple
* signal engine

## Sprint 4 — Paper broker

* órdenes paper
* fills
* posiciones
* PnL
* sizing rules

## Sprint 5 — Backtester

* replay engine
* strategy run
* métricas

## Sprint 6 — API + UI

* market explorer
* market detail
* portfolio
* backtests

## Sprint 7 — Hardening

* observability
* docs
* e2e
* polish

---

## 27. Qué pedirle a Codex o Claude Code

## Rol deseado del agente

Pedirle que actúe como:

**ingeniero de software senior / arquitecto de sistemas con foco en clean architecture, TDD, diseño modular, alta testabilidad, dominio financiero y pensamiento sistémico.**

## Prompt marco sugerido

```text
Actúa como un Staff Software Engineer / Systems Architect.
Diseña e implementa este producto con enfoque en:
- Clean Architecture / Hexagonal Architecture
- SOLID
- Domain modeling explícito
- TDD estricto
- alta cobertura de tests en módulos críticos
- documentación clara mediante tests, ADRs y notas técnicas de dominio/matemática
- interfaces desacopladas y repositorios por contrato
- evitar sobreingeniería y mantener MVP feasible

Prioriza:
1. dominio y reglas de negocio
2. tests pedagógicos y robustos
3. documentación técnica semi-académica cuando aporte comprensión
4. casos de uso bien separados
5. adapters reemplazables
6. trazabilidad y explicabilidad

No implementes live trading en la primera fase.
No mezcles infraestructura con dominio.
No uses LLMs como dependencia central del core.
Cada PR lógico debe incluir tests y explicación de decisiones.

Cuando el módulo involucre probabilidad, estadística, pricing, sizing, PnL, scoring o backtesting, incluye además notas técnicas breves con intuición matemática y fórmulas en LaTeX si mejoran la comprensión.
```

## Instrucciones de flujo para el agente

```text
Para cada tarea:
1. propone plan breve
2. enumera archivos a crear/modificar
3. escribe primero tests
4. implementa mínimo necesario
5. refactoriza si corresponde
6. valida con test suite
7. deja notas técnicas y ADR si hubo decisión importante
```

---

## 28. Definición de done

Una tarea no está terminada si solo “funciona”. Debe además:

* tener tests relevantes
* pasar lint y type checks
* respetar capas
* no introducir dependencias cíclicas
* exponer errores de forma clara
* tener nombres consistentes con el dominio
* dejar trazabilidad suficiente

---

## 29. Próximos pasos recomendados

1. congelar este alcance MVP
2. crear ADRs iniciales
3. generar esqueleto del repositorio
4. implementar primero dominio + tests
5. luego primer adapter real
6. luego signal engine
7. luego paper broker
8. luego backtesting
9. luego API/UI

---

## 30. Conclusión

Este producto es **ambicioso pero feasible** para un solo desarrollador apoyado por Codex o Claude Code, siempre que se respete una disciplina fuerte de alcance y TDD.

La clave no es intentar construir un “hedge fund engine” desde el inicio, sino un sistema que:

* modele bien el dominio,
* sea confiable,
* enseñe mediante sus tests,
* y permita evolucionar hacia mayor sofisticación sin reescribir todo.

La mejor versión del MVP no es la más compleja. Es la más **clara, extensible, testeada y honesta** sobre lo que sabe y lo que no sabe.
