# Especificación Técnica — Generación de la Base de Datos
## Demo "Verifiquemos · Comportamiento, patrones y proyecciones" — Banrural

> **Para Claude Code.** Este documento es el plano completo para construir y poblar la base de datos del demo. Léelo entero antes de escribir código.

---

## 0. Contexto en una página

Se está construyendo una **demostración** para la junta directiva de un banco (caso hipotético: Banrural). La tesis del producto es:

> **"Verifiquemos vio una señal que el banco no podía ver → y esa señal anticipó un riesgo o una oportunidad."**

Un asistente de IA conversará por voz con directivos y responderá preguntas sobre la cartera. Para que eso funcione, **los datos deben contener de verdad los patrones que el asistente va a "descubrir"**. No se trata de datos aleatorios: se trata de datos **sembrados** con patrones específicos y **coherentes entre sí**.

### La regla de oro

> **Cada cliente debe ser una historia internamente consistente a través de las seis fuentes de datos.**

Un cliente NO puede tener: score excelente + VERITAS categoría A + cero atrasos + **proyección de mora del 85%**. Eso es incoherente y destruiría la credibilidad del demo. La coherencia cruzada es el requisito más importante de esta especificación.

### Entorno

- **Motor:** PostgreSQL 18, local
- **Base:** `demoscoring` (host `localhost`, puerto `5432`, usuario `postgres`)
- **Volumen:** ~25,000 clientes, 5 años de historia (2021–2025), 2 corridas de monitoreo por cliente
- **Directorio de trabajo:** `C:\Develop\demoscoring`

---

## 1. Las seis fuentes de datos

| # | Fuente | Qué aporta | Aplica a |
|---|---|---|---|
| 1 | **Verifiquemos — originación** | Señal del día cero: score, OSINT, biometría, listas, PEP/CPE, riesgo geográfico | Todos |
| 2 | **Verifiquemos — monitoreo** | Segunda corrida: qué cambió (nuevos hits, nuevo PEP, adverse media nueva, deriva de score) | Todos |
| 3 | **Comportamiento real (core)** | El desenlace: atrasos, si terminó de pagar, cobro legal, seguro | Todos |
| 4 | **VERITAS** | Análisis crediticio: scoring, comportamiento, dependencia, capacidad de pago | **Solo créditos** |
| 5 | **Datos del solicitante** | Tabla maestra: género, edad, estado civil, departamento, región, producto, monto | Todos |
| 6 | **Proyección LSTM** | Probabilidad de mora a 12 meses + factores explicativos | **Solo créditos** |

**Llave que une todo:** `codigo_unico` (PK en solicitante, FK en las demás).

---

## 2. Catálogos (valores permitidos)

### 2.1 Solicitante

```
GENERO:          Masculino | Femenino
ESTADO_CIVIL:    Soltero | Casado | Unido
EDAD:            18–70
TIPO_PRODUCTO:   Crédito Consumo | Crédito Pyme | Tarjeta de Crédito
PLAZO_MESES:     12 | 24 | 36 | 48 | 60   (no aplica a tarjeta)

MONTO_CREDITO:
  - Crédito Consumo: Q1,000 – Q200,000
  - Crédito Pyme:    Q1,000 – Q1,000,000
  - Tarjeta:         NULL (no aplica)
```

> **Nota de realismo:** aunque el rango de Pyme permite desde Q1,000, la *distribución* debe concentrarse en Q50,000–Q500,000 (una pyme con crédito de Q1,000 se ve artificial). Usar distribución log-normal sesgada.

### 2.2 Geografía — 8 regiones y 22 departamentos

```
I   · Metropolitana   → Guatemala
II  · Norte           → Alta Verapaz, Baja Verapaz
III · Nororiente      → El Progreso, Izabal, Zacapa, Chiquimula
IV  · Suroriente      → Santa Rosa, Jalapa, Jutiapa
V   · Central         → Sacatepéquez, Chimaltenango, Escuintla
VI  · Suroccidente    → Sololá, Totonicapán, Quetzaltenango, Suchitepéquez, Retalhuleu, San Marcos
VII · Noroccidente    → Huehuetenango, Quiché
VIII· Petén           → Petén
```

### 2.3 Verifiquemos

```
PERFIL_INGRESOS (6):
  Q0 – Q3,000
  Q3,001 – Q10,000
  Q10,001 – Q50,000
  Q50,001 – Q100,000
  Q100,001 – Q200,000
  Q200,001+

ACTIVIDAD_ECONOMICA (18):
  Ama de casa | Asalariados | Casinos | Comercio en efectivo | Comercio general |
  Construcción | Estudiante | Exportación/Importación | Inmobiliarias |
  Jubilado/Pensionado | Joyerías y metales preciosos | Organizaciones sin fines de lucro |
  Profesionales independientes | Remesadoras | Servicios financieros | Transporte |
  Turismo y hotelería | Otros

PRODUCTO_SERVICIO (18):
  Activos virtuales | Auditoría | Blindaje | Casas de empeño | Compra/venta de divisas |
  Corretaje de valores | Cuentas activas: créditos | Cuentas pasivas: monetarias, ahorro, CDP |
  Factoraje | Fideicomisos | Remesas | Seguros y fianzas | Servicios de custodia |
  Tarjetas de crédito | Transferencias internacionales | Vehículos (compra/venta) |
  Vivienda/inmobiliario | Otros

CATEGORIA_CLIENTE (3):
  Nacional verificado en RENAP | Extranjero residente en Guatemala | Extranjero no residente

NATURALEZA: Persona Individual | Persona Jurídica

CONDICION_ESPECIAL (booleanos independientes):
  pep | pep_representante | pep_beneficiario_final | contratista_estado (CPE) |
  ong | fideicomiso | entidad_no_lucrativa | persona_obligada
  (pep_representante y pep_beneficiario_final solo aplican a Persona Jurídica)

LISTAS (5, cada una booleana): ofac | onu | engel | cpe | pep

RIESGO_GEOGRAFICO (3 booleanos):
  transferencias_internacionales | recibe_de_sancionados | envia_a_sancionados

OSINT:
  sentimiento:      Positivo | Neutral | Negativo
  categoria:        General | Noticias | Redes sociales | Listas | Criminal
  nivel_riesgo:     Sin riesgo | Bajo | Medio | Alto
  menciones:        entero (0–20)

BIOMETRIA: coincidencia_facial 0–100 (%)

SCORE: 0–100, compuesto por 7 subfactores (con sus máximos):
  identidad_listas (30) | riesgo_geografico (15) | perfil_ingresos (5) |
  actividad_economica (15) | condicion_especial (15) | naturaleza_cliente (10) |
  producto_servicio (10)
  ⚠️ El score total DEBE ser la suma exacta de los 7 subfactores.

BANDAS_SCORE:  Bajo 0–30 | Medio 31–50 | Medio-alto 51–70 | Alto 71–100
NIVEL_RIESGO:  Bajo | Medio | Alto
RECOMENDACION: Aprobar | Revisar | Rechazar
```

### 2.4 VERITAS *(solo créditos)*

```
scoring_crediticio:      30–100
comportamiento_pago:     A | B | C
dependencia_clientes:    0–100 (%)
capacidad_pago:          A (ratio >1.20 y <3) | B (ratio ≥1 y <1.20) | C (ratio <1)
```

### 2.5 Comportamiento real (core)

```
tuvo_atrasos:            boolean          (todos los productos)
cantidad_atrasos:        1–10 | NULL      (solo créditos; NULL si tuvo_atrasos=false)
termino_de_pagar:        boolean
termino_a_tiempo:        boolean | NULL   (NULL si termino_de_pagar=false)
cobro_legal:             boolean
tiene_seguro_vida_credito: boolean
```

### 2.6 Proyección LSTM *(solo créditos)*

```
probabilidad_mora:       0–100 (%)
horizonte_meses:         12 (fijo)
nivel_riesgo:            Bajo (<30) | Medio (30–60) | Alto (>60)
factores_explicativos:   array/JSON con los 2–4 factores de mayor peso
```

**Factores explicativos posibles** (usar los que realmente apliquen al cliente):
- *Financieros:* `atrasos_previos`, `capacidad_pago_veritas`, `sobreendeudamiento`, `cobro_legal_previo`
- *Verifiquemos:* `deriva_score`, `adverse_media`, `condicion_pep_cpe`, `riesgo_geografico_fondos`
- *Demográficos:* `edad`, `genero`, `estado_civil`
- *Geográficos:* `departamento`, `region`

---

## 3. Esquema de base de datos (DDL)

```sql
-- =====================================================================
-- BASE: demoscoring
-- =====================================================================

-- ---------- TABLA MAESTRA: SOLICITANTE ----------
CREATE TABLE solicitante (
    codigo_unico        VARCHAR(20) PRIMARY KEY,
    genero              VARCHAR(10)  NOT NULL,
    edad                SMALLINT     NOT NULL CHECK (edad BETWEEN 18 AND 70),
    departamento        VARCHAR(40)  NOT NULL,
    region              VARCHAR(30)  NOT NULL,
    estado_civil        VARCHAR(10)  NOT NULL,
    tipo_producto       VARCHAR(30)  NOT NULL,
    monto_credito       NUMERIC(12,2),          -- NULL para tarjeta
    plazo_meses         SMALLINT,               -- NULL para tarjeta
    fecha_originacion   DATE         NOT NULL,
    cohorte             SMALLINT     NOT NULL,  -- año de originación (2021–2025)
    arquetipo           VARCHAR(10)  NOT NULL,  -- trazabilidad interna (A1, B4, D1…)
    CONSTRAINT chk_monto_tarjeta CHECK (
        (tipo_producto = 'Tarjeta de Crédito' AND monto_credito IS NULL)
        OR (tipo_producto <> 'Tarjeta de Crédito' AND monto_credito IS NOT NULL)
    )
);

-- ---------- VERIFIQUEMOS: VALIDACIONES (2 corridas por cliente) ----------
CREATE TABLE validacion (
    id                      BIGSERIAL PRIMARY KEY,
    codigo_unico            VARCHAR(20) NOT NULL REFERENCES solicitante(codigo_unico),
    numero_corrida          SMALLINT    NOT NULL CHECK (numero_corrida IN (1,2)),
    fecha_corrida           DATE        NOT NULL,

    -- Identidad / perfil declarado
    naturaleza              VARCHAR(20) NOT NULL,
    categoria_cliente       VARCHAR(40) NOT NULL,
    actividad_economica     VARCHAR(50) NOT NULL,
    perfil_ingresos         VARCHAR(30) NOT NULL,
    producto_servicio       VARCHAR(60),

    -- Condiciones especiales
    pep                     BOOLEAN NOT NULL DEFAULT FALSE,
    pep_representante       BOOLEAN NOT NULL DEFAULT FALSE,
    pep_beneficiario_final  BOOLEAN NOT NULL DEFAULT FALSE,
    contratista_estado      BOOLEAN NOT NULL DEFAULT FALSE,
    ong                     BOOLEAN NOT NULL DEFAULT FALSE,
    fideicomiso             BOOLEAN NOT NULL DEFAULT FALSE,
    entidad_no_lucrativa    BOOLEAN NOT NULL DEFAULT FALSE,
    persona_obligada        BOOLEAN NOT NULL DEFAULT FALSE,

    -- Riesgo geográfico
    transferencias_internacionales BOOLEAN NOT NULL DEFAULT FALSE,
    recibe_de_sancionados          BOOLEAN NOT NULL DEFAULT FALSE,
    envia_a_sancionados            BOOLEAN NOT NULL DEFAULT FALSE,

    -- Listas de riesgo
    match_ofac              BOOLEAN NOT NULL DEFAULT FALSE,
    match_onu               BOOLEAN NOT NULL DEFAULT FALSE,
    match_engel             BOOLEAN NOT NULL DEFAULT FALSE,
    match_cpe               BOOLEAN NOT NULL DEFAULT FALSE,
    match_pep               BOOLEAN NOT NULL DEFAULT FALSE,

    -- Biometría
    coincidencia_facial     NUMERIC(5,2),   -- 0–100

    -- Incongruencia (flag derivado)
    mismatch_ingreso_actividad BOOLEAN NOT NULL DEFAULT FALSE,

    -- Score y subfactores (la suma DEBE dar score_total)
    sub_identidad_listas    SMALLINT NOT NULL CHECK (sub_identidad_listas   BETWEEN 0 AND 30),
    sub_riesgo_geografico   SMALLINT NOT NULL CHECK (sub_riesgo_geografico  BETWEEN 0 AND 15),
    sub_perfil_ingresos     SMALLINT NOT NULL CHECK (sub_perfil_ingresos    BETWEEN 0 AND 5),
    sub_actividad_economica SMALLINT NOT NULL CHECK (sub_actividad_economica BETWEEN 0 AND 15),
    sub_condicion_especial  SMALLINT NOT NULL CHECK (sub_condicion_especial BETWEEN 0 AND 15),
    sub_naturaleza_cliente  SMALLINT NOT NULL CHECK (sub_naturaleza_cliente BETWEEN 0 AND 10),
    sub_producto_servicio   SMALLINT NOT NULL CHECK (sub_producto_servicio  BETWEEN 0 AND 10),
    score_total             SMALLINT NOT NULL CHECK (score_total BETWEEN 0 AND 100),
    banda_score             VARCHAR(15) NOT NULL,  -- Bajo | Medio | Medio-alto | Alto
    nivel_riesgo            VARCHAR(10) NOT NULL,  -- Bajo | Medio | Alto
    recomendacion           VARCHAR(15) NOT NULL,  -- Aprobar | Revisar | Rechazar

    UNIQUE (codigo_unico, numero_corrida)
);

-- ---------- VERIFIQUEMOS: HALLAZGOS OSINT ----------
CREATE TABLE osint_hallazgo (
    id              BIGSERIAL PRIMARY KEY,
    codigo_unico    VARCHAR(20) NOT NULL REFERENCES solicitante(codigo_unico),
    numero_corrida  SMALLINT    NOT NULL CHECK (numero_corrida IN (1,2)),
    fuente          VARCHAR(80),
    categoria       VARCHAR(20) NOT NULL,  -- General|Noticias|Redes sociales|Listas|Criminal
    sentimiento     VARCHAR(10) NOT NULL,  -- Positivo|Neutral|Negativo
    nivel_riesgo    VARCHAR(12) NOT NULL,  -- Sin riesgo|Bajo|Medio|Alto
    comentario      TEXT
);

-- ---------- VERITAS (solo créditos) ----------
CREATE TABLE veritas (
    codigo_unico          VARCHAR(20) PRIMARY KEY REFERENCES solicitante(codigo_unico),
    scoring_crediticio    SMALLINT NOT NULL CHECK (scoring_crediticio BETWEEN 30 AND 100),
    comportamiento_pago   CHAR(1)  NOT NULL CHECK (comportamiento_pago IN ('A','B','C')),
    dependencia_clientes  NUMERIC(5,2) NOT NULL CHECK (dependencia_clientes BETWEEN 0 AND 100),
    capacidad_pago        CHAR(1)  NOT NULL CHECK (capacidad_pago IN ('A','B','C')),
    ratio_capacidad       NUMERIC(4,2) NOT NULL   -- valor numérico que sustenta la letra
);

-- ---------- COMPORTAMIENTO REAL (core bancario) ----------
CREATE TABLE comportamiento (
    codigo_unico              VARCHAR(20) PRIMARY KEY REFERENCES solicitante(codigo_unico),
    tuvo_atrasos              BOOLEAN NOT NULL,
    cantidad_atrasos          SMALLINT CHECK (cantidad_atrasos BETWEEN 1 AND 10),
    termino_de_pagar          BOOLEAN NOT NULL,
    termino_a_tiempo          BOOLEAN,
    cobro_legal               BOOLEAN NOT NULL DEFAULT FALSE,
    tiene_seguro_vida_credito BOOLEAN NOT NULL DEFAULT FALSE,
    en_mora                   BOOLEAN NOT NULL DEFAULT FALSE,  -- estado actual (derivado)
    meses_hasta_mora          SMALLINT,                        -- NULL si nunca cayó en mora
    alerta_aml                BOOLEAN NOT NULL DEFAULT FALSE,
    saldo_expuesto            NUMERIC(12,2),                   -- para "monto expuesto"
    CONSTRAINT chk_atrasos CHECK (
        (tuvo_atrasos = FALSE AND cantidad_atrasos IS NULL)
        OR (tuvo_atrasos = TRUE AND cantidad_atrasos IS NOT NULL)
    ),
    CONSTRAINT chk_termino CHECK (
        (termino_de_pagar = FALSE AND termino_a_tiempo IS NULL)
        OR (termino_de_pagar = TRUE AND termino_a_tiempo IS NOT NULL)
    )
);

-- ---------- PROYECCIÓN LSTM (solo créditos) ----------
CREATE TABLE proyeccion_mora (
    codigo_unico          VARCHAR(20) PRIMARY KEY REFERENCES solicitante(codigo_unico),
    probabilidad_mora     NUMERIC(5,2) NOT NULL CHECK (probabilidad_mora BETWEEN 0 AND 100),
    horizonte_meses       SMALLINT NOT NULL DEFAULT 12,
    nivel_riesgo          VARCHAR(10) NOT NULL,  -- Bajo | Medio | Alto
    factores_explicativos JSONB NOT NULL         -- ["atrasos_previos","capacidad_pago_veritas",...]
);

-- ---------- ÍNDICES (CRÍTICOS para el rendimiento en vivo) ----------
CREATE INDEX idx_val_codigo         ON validacion(codigo_unico);
CREATE INDEX idx_val_corrida        ON validacion(numero_corrida);
CREATE INDEX idx_val_banda          ON validacion(banda_score);
CREATE INDEX idx_val_pep            ON validacion(pep) WHERE pep = TRUE;
CREATE INDEX idx_val_listas         ON validacion(match_ofac, match_onu, match_engel);
CREATE INDEX idx_osint_codigo       ON osint_hallazgo(codigo_unico);
CREATE INDEX idx_osint_categoria    ON osint_hallazgo(categoria);
CREATE INDEX idx_osint_sentimiento  ON osint_hallazgo(sentimiento);
CREATE INDEX idx_sol_cohorte        ON solicitante(cohorte);
CREATE INDEX idx_sol_region         ON solicitante(region);
CREATE INDEX idx_sol_depto          ON solicitante(departamento);
CREATE INDEX idx_sol_producto       ON solicitante(tipo_producto);
CREATE INDEX idx_sol_arquetipo      ON solicitante(arquetipo);
CREATE INDEX idx_comp_mora          ON comportamiento(en_mora);
CREATE INDEX idx_proy_prob          ON proyeccion_mora(probabilidad_mora);
CREATE INDEX idx_proy_nivel         ON proyeccion_mora(nivel_riesgo);
```

---

## 4. Los 22 arquetipos

Cada arquetipo es una **receta de coherencia cruzada**. El campo `arquetipo` en `solicitante` guarda cuál se usó (para trazabilidad y verificación).

> **Importante:** los porcentajes suman más de 100% porque se permite **solapamiento controlado (~10–15%)**: un cliente puede combinar rasgos de dos arquetipos (ej. C4 demográfico + A1 adverse media). Esto es deseable: hace la cartera realista. Implementar como: asignar arquetipo primario según pesos, y con probabilidad ~12% inyectar rasgos de un arquetipo secundario compatible.

### Grupo A — Riesgo por señal de originación (el día cero predijo)

| ID | Nombre | Perfil coherente | % |
|----|--------|------------------|---|
| **A1** | **La bomba silenciosa** | OSINT: menciones negativas, categoría Noticias/Criminal, nivel Medio/Alto · score medio (31–50) · CORE: cae en mora ~18 meses, `alerta_aml` frecuente · VERITAS: B/C · LSTM: alto | 6% |
| **A2** | **Fraude de identidad** | `coincidencia_facial` < 85 · score alto · CORE: default temprano (`meses_hasta_mora` < 6), `cobro_legal` frecuente · VERITAS: C | 3% |
| **A3** | **Incongruencia ingreso-actividad** | `mismatch_ingreso_actividad = TRUE` (ej. actividad "Estudiante"/"Ama de casa" con ingresos Q50,001+) · CORE: mora · VERITAS: capacidad C | 7% |
| **A4** | **PEP peligroso** | `pep = TRUE` + `match_pep = TRUE` + OSINT negativo · CORE: ~33% en mora · LSTM: alto | 1.5% |
| **A5** | **Flujos sancionados** | `recibe_de_sancionados` y/o `envia_a_sancionados = TRUE` · actividad: Exportación/Importación o Compra/venta de divisas · OSINT adverso · CORE: `alerta_aml = TRUE` | 2% |

### Grupo B — Riesgo detectado por monitoreo (delta entre corrida 1 y 2)

| ID | Nombre | Perfil coherente | % |
|----|--------|------------------|---|
| **B1** | **Hit nuevo en listas** | Corrida 1: todas las listas limpias → **Corrida 2: `match_ofac` o `match_onu` = TRUE** · CORE: crédito vigente (no terminó de pagar) | 0.1% |
| **B2** | **Se volvió PEP** | Corrida 1: `pep = FALSE` → **Corrida 2: `pep = TRUE`** · CORE: crédito vigente | 1% |
| **B3** | **Adverse media nueva** | Corrida 1: sin OSINT negativo → **Corrida 2: menciones negativas** (algunas categoría Criminal) · producto reciente | 0.8% |
| **B4** | ⭐ **Deteriorado silencioso** | Corrida 1: **score bajo (0–30), limpio** → Corrida 2: score sube a Medio/Medio-alto, aparecen señales · CORE: **aún sin mora** · LSTM: **> 65%** | 1% |

> **B4 es el escenario estrella**: "clientes que pasaron limpios en el onboarding pero que el modelo ahora ve en riesgo". Debe producir ~210 clientes.

### Grupo C — Riesgo por crédito y comportamiento

| ID | Nombre | Perfil coherente | % |
|----|--------|------------------|---|
| **C1** | **Sobreendeudado** | VERITAS: `capacidad_pago = C`, `comportamiento_pago = C` · CORE: `cantidad_atrasos` 5–10 · LSTM: alto | 4% |
| **C2** | **Cobro legal** | CORE: `cobro_legal = TRUE`, `termino_de_pagar = FALSE`, muchos atrasos · VERITAS: C · alguna señal VQ | 1.5% |
| **C3** | **CPE flujo apretado** | `contratista_estado = TRUE` + `match_cpe = TRUE` · CORE: atrasos cíclicos (2–4) pero **termina pagando** · VERITAS: `dependencia_clientes` alta (>70) | 2.5% |
| **C4** | **Demográfico de riesgo** | SOL: **Soltero, edad 18–30, región Noroccidente** · producto: Crédito Consumo · CORE: mora · LSTM: alto (factor demográfico presente) | 3% |
| **C5** | **Dependencia concentrada** | Producto: Crédito Pyme · VERITAS: `dependencia_clientes > 70` · CORE: atrasos irregulares | 1.5% |
| **C6** | **Riesgo medio sin seguro** | VERITAS: B · CORE: 1–3 atrasos, aún pagando, **`tiene_seguro_vida_credito = FALSE`** · LSTM: medio (30–60%) | 13% |
| **C7** | **Revolvente atrapado** | Producto: **Tarjeta de Crédito** · CORE: `tuvo_atrasos = TRUE`, atrasos crecientes · VERITAS: N/A (tarjeta) · LSTM: N/A | 3% |

> **C6 debe producir ~3,200 deudores** de riesgo medio sin seguro (escenario de colocación de seguros).

### Grupo D — Comercial (oportunidad)

| ID | Nombre | Perfil coherente | % |
|----|--------|------------------|---|
| **D1** | ⭐ **Sano ejemplar** | Score **bajo (0–30)** · 5 listas limpias · `coincidencia_facial > 92` · **sin OSINT negativo** · `mismatch = FALSE` · CORE: sin atrasos · VERITAS: A/A · LSTM: **< 10%** | 17% |
| **D2** | **Empresario oculto** | `naturaleza = Persona Individual` **pero** OSINT revela actividad comercial (categoría General, fuente tipo directorio/proveedor, sentimiento Positivo/Neutral) · CORE: buen pago | 4.5% |
| **D3** | **Evolucionó bien** | Corrida 1: score medio → **Corrida 2: score mejora**, OSINT positivo/neutro · CORE: `termino_de_pagar = TRUE`, `termino_a_tiempo = TRUE` · LSTM: bajó | 3% |
| **D4** | **Internacional** | `categoria_cliente` = Extranjero residente / no residente · actividad: Exportación/Importación · `transferencias_internacionales = TRUE` **pero sin sancionados** · CORE: buen pago | 3.5% |

> **D1 debe producir ~4,300 clientes** pre-cualificados (17% de 25,000).

### Grupo E — Contrapartes y masa (dan realismo y contraste)

| ID | Nombre | Perfil coherente | % |
|----|--------|------------------|---|
| **E1** | **PEP inofensivo** | `pep = TRUE` + `match_pep = TRUE` · **sin OSINT negativo** · score bajo · CORE: buen pago (~8% mora) · LSTM: bajo | 6% |
| **E2** | **Promedio / neutro** | Todo en rangos medios · sin señales · CORE: 0–1 atraso leve · VERITAS: B · LSTM: bajo/medio | 25% |
| **E3** | **Buen pagador cerrado** | CORE: `termino_de_pagar = TRUE`, `termino_a_tiempo = TRUE`, `tuvo_atrasos = FALSE` · VERITAS: A · cosechas antiguas (2021–2022) | 6% |

> **E1 vs A4 es el contraste clave**: PEP sin adverse media ≈ 8% de mora; PEP con adverse media ≈ 33% de mora.

---

## 5. Las 6 reglas transversales de distribución

Estas **no son tipos de cliente** — son leyes que gobiernan la cartera completa. Sin ellas, varios escenarios del demo no funcionan.

### R1 · Curva de mora monótona por banda de score

La mora debe **escalar de forma creciente** con la banda de score de originación:

| Banda score | % de cartera | Tasa de mora objetivo |
|-------------|--------------|----------------------|
| Bajo (0–30) | 45% | ~4% |
| Medio (31–50) | 33% | ~11% |
| Medio-alto (51–70) | 16% | ~19% |
| Alto (71–100) | 6% | ~28% |

**Verificaciones que deben cumplirse:**
- Mora(Alto) / Mora(Bajo) ≈ **4.7×**
- El ~22% superior (Medio-alto + Alto) concentra ~**61% del saldo vencido**

### R2 · Deterioro de la calidad de originación por cosecha

El score promedio de originación **empeora año con año** (las cosechas recientes son peores):

| Cohorte | Score promedio | Multiplicador de flags adverse media |
|---------|----------------|--------------------------------------|
| 2021 | 31 | 1.0× (base) |
| 2022 | 34 | 1.3× |
| 2023 | 37 | 1.7× |
| 2024 | 41 | 2.0× |
| 2025 | 44 | 2.3× |

**Debe producir:** *"el score promedio subió de 31 a 44 y hay 2.3× más flags de adverse media"*

### R3 · Crecimiento anual de PEP (~10% interanual)

Los clientes **PEP con producto de crédito** crecen ~10% cada año:

| Año | PEP con crédito |
|-----|-----------------|
| 2021 | 1,200 |
| 2022 | 1,330 |
| 2023 | 1,480 |
| 2024 | 1,680 |
| 2025 | 1,900 |

(2026 proyectado: 2,100 — lo calcula el asistente, no se guarda.)

**Debe producir:** el gráfico de líneas de crecimiento PEP del documento de alcances.

### R4 · Distribución geográfica ponderada

Repartir clientes por departamento según peso poblacional-bancario aproximado. Referencia de la distribución del segmento pre-cualificado (D1) que debe salir:

| Departamento | Clientes D1 aprox. |
|--------------|--------------------|
| Guatemala | 1,450 |
| Quetzaltenango | 780 |
| Escuintla | 640 |
| Huehuetenango | 520 |
| Sacatepéquez | 410 |
| Otros | 500 |
| **Total** | **~4,300** |

**Además:** sembrar el sesgo de riesgo de C4 en **Noroccidente** (Huehuetenango, Quiché) — solteros de 18–30 ahí deben tener mora notablemente superior.

### R5 · Coherencia LSTM ↔ resto de fuentes ⚠️ (LA MÁS IMPORTANTE)

**`probabilidad_mora` NO puede ser aleatoria.** Debe calcularse como función de los demás campos del cliente:

```
probabilidad_mora = f(
    atrasos_previos          (peso alto),
    capacidad_pago_veritas   (C sube mucho, A baja mucho),
    comportamiento_veritas   (C sube),
    score_verifiquemos       (banda alta sube),
    adverse_media            (sube),
    delta_score_entre_corridas (deriva negativa sube),
    condicion_pep_cpe        (sube levemente),
    riesgo_geografico_fondos (sube),
    perfil_demografico       (soltero joven en Noroccidente sube),
    edad                     (extremos suben levemente)
) + ruido_controlado(±5)
```

**Reglas duras:**
- Un cliente D1 (sano ejemplar) **nunca** puede tener probabilidad > 15%
- Un cliente C1 (sobreendeudado) **nunca** puede tener probabilidad < 50%
- Los `factores_explicativos` guardados deben ser **los que realmente pesaron** en ese cliente (los de mayor contribución en la fórmula). No inventar factores que el cliente no tiene.
- `nivel_riesgo` debe derivarse de `probabilidad_mora`: Bajo <30, Medio 30–60, Alto >60.

**Excepción intencional:** el arquetipo **B4** (deteriorado silencioso) tiene score de originación bajo pero LSTM alto — esto **no es incoherencia**, es el resultado del deterioro detectado en la corrida 2. La fórmula debe reflejarlo vía `delta_score_entre_corridas`.

### R6 · Línea temporal por cliente

Cada cliente tiene:
- **`fecha_originacion`** distribuida entre 2021 y 2025 (con más volumen en años recientes)
- **Corrida 1:** en la fecha de originación (la "foto del día cero")
- **Corrida 2:** una corrida de monitoreo posterior (misma fecha de referencia para todos, ej. reciente)
- **Comportamiento** desplegado en el tiempo (`meses_hasta_mora` relativo a la originación)

Los arquetipos B1–B4 y D3 se definen precisamente por **qué cambió entre corrida 1 y corrida 2**. Para el resto de clientes, la corrida 2 es igual o muy similar a la 1 (con variación mínima).

---

## 6. Estrategia de generación (implementación)

### Orden de ejecución

1. **Crear esquema** (DDL de la sección 3)
2. **Generar solicitantes** — asignar arquetipo según pesos, aplicar R4 (geografía) y R6 (fechas/cohortes)
3. **Generar validaciones corrida 1** — según la receta del arquetipo + R2 (deterioro por cosecha)
4. **Generar validaciones corrida 2** — igual a la 1, EXCEPTO para arquetipos B1–B4 y D3 (que cambian)
5. **Generar OSINT** — coherente con el arquetipo y la corrida
6. **Generar VERITAS** — solo para créditos, coherente con el arquetipo
7. **Generar comportamiento** — coherente con el arquetipo + R1 (curva de mora por banda)
8. **Calcular proyección LSTM** — aplicando R5 (fórmula sobre los datos ya generados) ← **debe ir al final**
9. **Ejecutar verificación** (sección 7)

### Notas técnicas

- **Lenguaje sugerido:** Python (con `psycopg` o `psycopg2`) o Node. Elige lo que prefieras.
- **Inserción:** usar **COPY** o batch inserts. Insertar fila por fila 25,000+ veces es innecesariamente lento.
- **Semilla aleatoria fija** (`random.seed(42)` o equivalente) para que la generación sea **reproducible**. Importante: si hay que recalibrar, queremos poder repetir.
- **Idempotencia:** el script debe poder correrse varias veces (DROP + CREATE, o TRUNCATE previo).
- **`codigo_unico`:** formato sugerido `CLI-000001` … `CLI-025000`.
- El campo `arquetipo` es interno (trazabilidad); no se muestra al usuario final del demo, pero es esencial para verificar.

---

## 7. Script de verificación (NO OPCIONAL)

Al terminar de generar, ejecutar un script que corra **las 21 preguntas del demo** contra los datos y confirme que cada cifra sale. Si alguna no cuadra, **ajustar pesos y regenerar**.

### Verificaciones obligatorias

```sql
-- V1 · Curva de mora monótona por banda (R1)
--     Debe ser CRECIENTE: Bajo < Medio < Medio-alto < Alto
--     Y ratio Alto/Bajo ≈ 4.7×
SELECT v.banda_score,
       COUNT(*) AS clientes,
       ROUND(100.0 * SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mora
FROM validacion v
JOIN comportamiento c USING (codigo_unico)
WHERE v.numero_corrida = 1
GROUP BY v.banda_score
ORDER BY MIN(v.score_total);

-- V2 · Adverse media predice mora (~41% vs ~9%)
SELECT CASE WHEN o.codigo_unico IS NOT NULL THEN 'Con adverse media' ELSE 'Sin adverse media' END AS grupo,
       COUNT(*) AS clientes,
       ROUND(100.0 * SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mora
FROM comportamiento c
LEFT JOIN (SELECT DISTINCT codigo_unico FROM osint_hallazgo
           WHERE sentimiento = 'Negativo' AND categoria IN ('Criminal','Noticias','Listas')) o
       USING (codigo_unico)
GROUP BY 1;

-- V3 · Biometría baja → más fraude/default temprano (~6×)
SELECT CASE WHEN v.coincidencia_facial < 85 THEN 'Facial < 85' ELSE 'Facial >= 85' END AS grupo,
       COUNT(*) AS clientes,
       ROUND(100.0 * SUM(CASE WHEN c.meses_hasta_mora < 6 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_default_temprano
FROM validacion v JOIN comportamiento c USING (codigo_unico)
WHERE v.numero_corrida = 1
GROUP BY 1;

-- V4 · PEP peligroso vs PEP inofensivo (~33% vs ~8%)
SELECT s.arquetipo, COUNT(*) AS clientes,
       ROUND(100.0 * SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mora
FROM solicitante s JOIN comportamiento c USING (codigo_unico)
WHERE s.arquetipo IN ('A4','E1')
GROUP BY s.arquetipo;

-- V5 · Deterioro de originación por cosecha (R2): score sube 31 → 44
SELECT s.cohorte, ROUND(AVG(v.score_total),1) AS score_promedio, COUNT(*) AS clientes
FROM solicitante s JOIN validacion v USING (codigo_unico)
WHERE v.numero_corrida = 1
GROUP BY s.cohorte ORDER BY s.cohorte;

-- V6 · Crecimiento PEP ~10% interanual (R3)
SELECT s.cohorte, COUNT(*) AS pep_con_credito
FROM solicitante s JOIN validacion v USING (codigo_unico)
WHERE v.numero_corrida = 1 AND v.pep = TRUE
  AND s.tipo_producto IN ('Crédito Consumo','Crédito Pyme')
GROUP BY s.cohorte ORDER BY s.cohorte;

-- V7 · Segmento pre-cualificado D1 (~4,300)
SELECT COUNT(*) FROM solicitante WHERE arquetipo = 'D1';

-- V8 · Deteriorado silencioso B4 (~210, limpios al inicio pero LSTM > 65%)
SELECT COUNT(*) FROM solicitante s
JOIN validacion v1 ON v1.codigo_unico = s.codigo_unico AND v1.numero_corrida = 1
JOIN proyeccion_mora p ON p.codigo_unico = s.codigo_unico
WHERE v1.banda_score = 'Bajo' AND p.probabilidad_mora > 65;

-- V9 · Riesgo medio sin seguro C6 (~3,200)
SELECT COUNT(*) FROM comportamiento c JOIN proyeccion_mora p USING (codigo_unico)
WHERE c.tiene_seguro_vida_credito = FALSE AND p.nivel_riesgo = 'Medio';

-- V10 · VERITAS predijo la mora (C ~38% vs A ~6%)
SELECT ve.comportamiento_pago, COUNT(*) AS clientes,
       ROUND(100.0 * SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mora
FROM veritas ve JOIN comportamiento c USING (codigo_unico)
GROUP BY ve.comportamiento_pago ORDER BY ve.comportamiento_pago;

-- V11 · Coherencia LSTM (R5) — NO deben existir resultados
--       Sanos con probabilidad alta, o sobreendeudados con probabilidad baja
SELECT 'INCOHERENCIA: D1 con prob alta' AS problema, COUNT(*)
FROM solicitante s JOIN proyeccion_mora p USING (codigo_unico)
WHERE s.arquetipo = 'D1' AND p.probabilidad_mora > 15
UNION ALL
SELECT 'INCOHERENCIA: C1 con prob baja', COUNT(*)
FROM solicitante s JOIN proyeccion_mora p USING (codigo_unico)
WHERE s.arquetipo = 'C1' AND p.probabilidad_mora < 50;

-- V12 · Perfil demográfico de riesgo C4 (soltero joven Noroccidente)
SELECT ROUND(100.0 * SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mora,
       COUNT(*) AS clientes
FROM solicitante s JOIN comportamiento c USING (codigo_unico)
WHERE s.estado_civil = 'Soltero' AND s.edad BETWEEN 18 AND 30
  AND s.region = 'Noroccidente' AND s.tipo_producto = 'Crédito Consumo';

-- V13 · Integridad del score: la suma de subfactores = score_total
SELECT COUNT(*) AS errores_score FROM validacion
WHERE score_total <> (sub_identidad_listas + sub_riesgo_geografico + sub_perfil_ingresos
                    + sub_actividad_economica + sub_condicion_especial
                    + sub_naturaleza_cliente + sub_producto_servicio);
-- DEBE dar 0

-- V14 · Integridad referencial: todo crédito tiene VERITAS y LSTM; tarjeta NO
SELECT 'Créditos sin VERITAS' AS problema, COUNT(*)
FROM solicitante s LEFT JOIN veritas v USING (codigo_unico)
WHERE s.tipo_producto <> 'Tarjeta de Crédito' AND v.codigo_unico IS NULL
UNION ALL
SELECT 'Tarjetas CON VERITAS (no debería)', COUNT(*)
FROM solicitante s JOIN veritas v USING (codigo_unico)
WHERE s.tipo_producto = 'Tarjeta de Crédito';
-- AMBOS deben dar 0
```

### Criterio de aceptación

La generación se considera **exitosa** cuando:

- ✅ V1 muestra una curva **estrictamente creciente** y ratio Alto/Bajo entre 4× y 5.5×
- ✅ V2 muestra un contraste marcado (con adverse media ≈ 3–4× más mora)
- ✅ V4 muestra A4 >> E1 (PEP peligroso vs inofensivo)
- ✅ V5 muestra score promedio creciente año a año (~31 → ~44)
- ✅ V6 muestra crecimiento PEP ≈ 10% interanual
- ✅ V7 ≈ 4,300 · V8 ≈ 210 · V9 ≈ 3,200 (±15% es aceptable)
- ✅ V10 muestra C >> A
- ✅ **V11, V13 y V14 dan CERO** (sin incoherencias — esto es no negociable)
- ✅ V12 muestra mora claramente superior al promedio de la cartera

**Si alguna falla:** ajustar los pesos/parámetros del arquetipo correspondiente y regenerar. No avanzar al siguiente paso hasta que todas pasen.

---

## 8. Entregables esperados

1. **`schema.sql`** — DDL completo (tablas + índices)
2. **`generate.py`** (o `.js`) — generador de datos con semilla fija
3. **`verify.sql`** (o script) — las verificaciones de la sección 7
4. **`README.md`** — cómo ejecutar todo
5. **Reporte de verificación** — salida de las 14 verificaciones, confirmando que los criterios se cumplen

---

## 9. Recordatorio final

> El demo NO consiste en que la IA invente cifras.
> Consiste en que la IA **descubra en los datos** patrones que **realmente sembramos ahí**.
>
> Si la generación de datos falla, el demo entero falla — por muy bueno que sea el modelo de IA.
> Por eso la sección 7 (verificación) no es opcional.
