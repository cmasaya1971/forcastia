-- =====================================================================
-- BASE: demoscoring
-- Demo "Verifiquemos · Comportamiento, patrones y proyecciones" — Banrural
-- Esquema completo (6 tablas + índices). Idempotente: DROP + CREATE.
-- =====================================================================

DROP TABLE IF EXISTS proyeccion_mora  CASCADE;
DROP TABLE IF EXISTS comportamiento   CASCADE;
DROP TABLE IF EXISTS veritas          CASCADE;
DROP TABLE IF EXISTS osint_hallazgo   CASCADE;
DROP TABLE IF EXISTS validacion       CASCADE;
DROP TABLE IF EXISTS solicitante      CASCADE;

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
