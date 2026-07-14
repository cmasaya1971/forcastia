# -*- coding: utf-8 -*-
"""
Generador de datos para el demo "Verifiquemos · Banrural" (base demoscoring).

Filosofía (ver ESPECIFICACION_GENERACION_DATOS.md):
  - Cada cliente es una HISTORIA internamente consistente a través de las 6 fuentes.
  - Los patrones se SIEMBRAN, no son aleatorios.
  - La proyección LSTM (probabilidad_mora) se calcula AL FINAL como función del resto.

Orden: solicitante -> validacion(1,2) -> osint -> veritas -> comportamiento -> proyeccion_mora.

Reproducible: random.seed(SEED). Inserción por COPY. Idempotente: TRUNCATE previo.
"""

import os
import sys
import json
import random
import datetime as dt

import psycopg

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
SEED = 42
N_CLIENTES = 25000
CORRIDA2_FECHA = dt.date(2026, 6, 30)   # fecha de referencia de monitoreo (reciente)

DATABASE_URL = os.environ.get("DATABASE_URL")   # Neon/Supabase en la nube (opcional)
DSN = dict(
    host=os.environ.get("PGHOST", "localhost"),
    port=int(os.environ.get("PGPORT", "5432")),
    user=os.environ.get("PGUSER", "postgres"),
    password=os.environ.get("PGPASSWORD", ""),
    dbname=os.environ.get("PGDATABASE", "demoscoring"),
)

def _connect():
    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL)
    return psycopg.connect(**DSN)

random.seed(SEED)

# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------
GENEROS = ["Masculino", "Femenino"]
ESTADOS_CIVILES = ["Soltero", "Casado", "Unido"]

# Geografía: 8 regiones, 22 departamentos
REGION_DEPTOS = {
    "Metropolitana": ["Guatemala"],
    "Norte": ["Alta Verapaz", "Baja Verapaz"],
    "Nororiente": ["El Progreso", "Izabal", "Zacapa", "Chiquimula"],
    "Suroriente": ["Santa Rosa", "Jalapa", "Jutiapa"],
    "Central": ["Sacatepéquez", "Chimaltenango", "Escuintla"],
    "Suroccidente": ["Sololá", "Totonicapán", "Quetzaltenango", "Suchitepéquez",
                     "Retalhuleu", "San Marcos"],
    "Noroccidente": ["Huehuetenango", "Quiché"],
    "Petén": ["Petén"],
}
DEPTO_REGION = {d: r for r, ds in REGION_DEPTOS.items() for d in ds}

# Pesos poblacional-bancarios aproximados por departamento (R4)
DEPTO_PESO = {
    "Guatemala": 30.0, "Quetzaltenango": 9.0, "Escuintla": 8.0, "Huehuetenango": 7.0,
    "Sacatepéquez": 5.0, "Alta Verapaz": 5.0, "San Marcos": 5.0, "Quiché": 4.0,
    "Suchitepéquez": 3.0, "Chimaltenango": 3.0, "Jutiapa": 3.0, "Petén": 2.5,
    "Izabal": 2.5, "Santa Rosa": 2.0, "Jalapa": 2.0, "Chiquimula": 2.0,
    "Totonicapán": 2.0, "Sololá": 2.0, "Retalhuleu": 2.0, "Zacapa": 1.5,
    "Baja Verapaz": 1.5, "El Progreso": 1.5,
}
DEPTOS = list(DEPTO_PESO.keys())
DEPTO_PESOS = list(DEPTO_PESO.values())

PERFILES_INGRESOS = [
    "Q0 – Q3,000", "Q3,001 – Q10,000", "Q10,001 – Q50,000",
    "Q50,001 – Q100,000", "Q100,001 – Q200,000", "Q200,001+",
]
PERFIL_ALTO = ["Q50,001 – Q100,000", "Q100,001 – Q200,000", "Q200,001+"]

ACTIVIDADES = [
    "Ama de casa", "Asalariados", "Casinos", "Comercio en efectivo", "Comercio general",
    "Construcción", "Estudiante", "Exportación/Importación", "Inmobiliarias",
    "Jubilado/Pensionado", "Joyerías y metales preciosos", "Organizaciones sin fines de lucro",
    "Profesionales independientes", "Remesadoras", "Servicios financieros", "Transporte",
    "Turismo y hotelería", "Otros",
]
# Riesgo intrínseco de la actividad (0-1) para el subfactor actividad_economica
ACTIVIDAD_RIESGO = {
    "Casinos": 0.9, "Joyerías y metales preciosos": 0.85, "Remesadoras": 0.8,
    "Exportación/Importación": 0.7, "Servicios financieros": 0.6, "Comercio en efectivo": 0.6,
    "Inmobiliarias": 0.55, "Turismo y hotelería": 0.4, "Construcción": 0.45,
    "Transporte": 0.4, "Comercio general": 0.35, "Profesionales independientes": 0.3,
    "Organizaciones sin fines de lucro": 0.35, "Asalariados": 0.15,
    "Jubilado/Pensionado": 0.1, "Ama de casa": 0.15, "Estudiante": 0.2, "Otros": 0.3,
}
ACTIVIDAD_PESOS = [max(1, int(60 * (1 - ACTIVIDAD_RIESGO[a]))) for a in ACTIVIDADES]

PRODUCTOS_SERVICIO = [
    "Activos virtuales", "Auditoría", "Blindaje", "Casas de empeño",
    "Compra/venta de divisas", "Corretaje de valores", "Cuentas activas: créditos",
    "Cuentas pasivas: monetarias, ahorro, CDP", "Factoraje", "Fideicomisos", "Remesas",
    "Seguros y fianzas", "Servicios de custodia", "Tarjetas de crédito",
    "Transferencias internacionales", "Vehículos (compra/venta)", "Vivienda/inmobiliario",
    "Otros",
]
PRODSERV_RIESGO = {
    "Activos virtuales": 0.9, "Casas de empeño": 0.75, "Compra/venta de divisas": 0.8,
    "Corretaje de valores": 0.6, "Servicios de custodia": 0.6, "Factoraje": 0.5,
    "Transferencias internacionales": 0.7, "Fideicomisos": 0.5, "Remesas": 0.55,
    "Blindaje": 0.5, "Vehículos (compra/venta)": 0.4, "Seguros y fianzas": 0.25,
    "Vivienda/inmobiliario": 0.3, "Cuentas activas: créditos": 0.2,
    "Cuentas pasivas: monetarias, ahorro, CDP": 0.15, "Tarjetas de crédito": 0.25,
    "Auditoría": 0.2, "Otros": 0.3,
}

CATEGORIAS_CLIENTE = [
    "Nacional verificado en RENAP", "Extranjero residente en Guatemala",
    "Extranjero no residente",
]

# ---------------------------------------------------------------------------
# Distribución temporal (R6): cosechas 2021-2025, más volumen reciente
# ---------------------------------------------------------------------------
COHORTES = [2021, 2022, 2023, 2024, 2025]
COHORTE_PESO = {2021: 0.12, 2022: 0.16, 2023: 0.20, 2024: 0.24, 2025: 0.28}

# R2: deterioro de la calidad de originación por cosecha (score sube 31 -> 44)
COHORTE_SCORE_OFFSET = {2021: 0, 2022: 3, 2023: 6, 2024: 10, 2025: 13}
# R2: multiplicador de adverse media por cosecha
COHORTE_ADVERSE_MULT = {2021: 1.0, 2022: 1.3, 2023: 1.7, 2024: 2.0, 2025: 2.3}

# R3: PEP con crédito por año (objetivo del crecimiento ~10% interanual)
PEP_CREDITO_OBJETIVO = {2021: 1200, 2022: 1330, 2023: 1480, 2024: 1680, 2025: 1900}

# ---------------------------------------------------------------------------
# Arquetipos: conteos EXACTOS (deterministas) — garantizan V7/V8/V9
# (porcentajes de la spec, con E2 como amortiguador para sumar 25,000)
# ---------------------------------------------------------------------------
ARQ_CONTEOS = {
    "A1": 1500, "A2": 750, "A3": 1750, "A4": 375, "A5": 500,
    "B1": 25, "B2": 250, "B3": 200, "B4": 210,
    "C1": 1000, "C2": 375, "C3": 625, "C4": 750, "C5": 375, "C6": 3200, "C7": 750,
    "D1": 4300, "D2": 1125, "D3": 750, "D4": 875,
    "E1": 1500, "E2": None, "E3": 1500,   # E2 se completa al final
}
_fijos = sum(v for v in ARQ_CONTEOS.values() if v is not None)
ARQ_CONTEOS["E2"] = N_CLIENTES - _fijos   # 2315
assert ARQ_CONTEOS["E2"] > 0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def banda_de(score):
    if score <= 30:
        return "Bajo"
    if score <= 50:
        return "Medio"
    if score <= 70:
        return "Medio-alto"
    return "Alto"

def nivel_de_banda(banda):
    return {"Bajo": "Bajo", "Medio": "Medio", "Medio-alto": "Medio", "Alto": "Alto"}[banda]

def recomendacion_de_banda(banda):
    return {"Bajo": "Aprobar", "Medio": "Aprobar",
            "Medio-alto": "Revisar", "Alto": "Rechazar"}[banda]

def nivel_lstm(prob):
    if prob < 30:
        return "Bajo"
    if prob <= 60:
        return "Medio"
    return "Alto"

def elegir_departamento():
    return random.choices(DEPTOS, weights=DEPTO_PESOS, k=1)[0]

def monto_consumo():
    v = random.lognormvariate(10.4, 0.75)   # centrado ~Q33k
    return round(min(max(v, 1000.0), 200000.0), 2)

def monto_pyme():
    v = random.lognormvariate(11.9, 0.7)     # centrado ~Q147k (concentra 50k-500k)
    return round(min(max(v, 1000.0), 1000000.0), 2)

def fecha_en_cohorte(cohorte):
    inicio = dt.date(cohorte, 1, 1)
    dias = 364
    return inicio + dt.timedelta(days=random.randint(0, dias))

# ---------------------------------------------------------------------------
# Definición de arquetipos: banda objetivo de score, producto, mora, veritas...
# mora: probabilidad objetivo de en_mora (se usa como base; None => usar banda)
# ---------------------------------------------------------------------------
# banda de score de originación (corrida 1) preferida por arquetipo
# (arquetipos de mayor mora -> bandas más altas, para que el score PREDIGA la mora)
ARQ_BANDA = {
    "A1": "Medio", "A2": "Alto", "A3": "Medio", "A4": "Alto", "A5": "Medio-alto",
    "B1": "Medio-alto", "B2": "Medio-alto", "B3": "Medio-alto", "B4": "Bajo",
    "C1": "Alto", "C2": "Medio-alto", "C3": "Medio", "C4": "Medio-alto",
    "C5": "Medio-alto", "C6": "Medio", "C7": "Medio-alto",
    "D1": "Bajo", "D2": "Bajo", "D3": "Medio", "D4": "Bajo",
    "E1": "Bajo", "E2": "Bajo", "E3": "Bajo",   # E2 se reparte Bajo/Medio en construir_score
}
# probabilidad objetivo de mora por arquetipo (calibrada a la curva R1:
# Bajo ~5 | Medio ~15 | Medio-alto ~22 | Alto ~28, ratio ~5x)
ARQ_MORA = {
    "A1": 0.35, "A2": 0.24, "A3": 0.14, "A4": 0.40, "A5": 0.25,
    "B1": 0.10, "B2": 0.10, "B3": 0.30, "B4": 0.0,   # B4: aún sin mora
    "C1": 0.26, "C2": 0.35, "C3": 0.10, "C4": 0.28, "C5": 0.15,
    "C6": 0.11, "C7": 0.15,
    "D1": 0.0, "D2": 0.08, "D3": 0.04, "D4": 0.08,
    "E1": 0.12, "E2": 0.19, "E3": 0.0,
}

# rangos de score por banda (bajos, para que 2021 promedie ~31 y con offset llegue a ~44)
BAND_RANGE = {"Bajo": (3, 20), "Medio": (33, 47),
              "Medio-alto": (52, 66), "Alto": (72, 88)}

# Diferenciación de producto por RIESGO DEL ARQUETIPO (no toca la mora por cliente,
# así la curva V1 queda intacta): los arquetipos más riesgosos tienden a Tarjeta de
# Crédito (revolvente) y los más sanos a Crédito Pyme. Como los clientes riesgosos se
# concentran en Tarjeta, ese producto muestra mayor mora — de forma coherente, no
# porque cambiemos su probabilidad.
def _pesos_producto(arq):
    r = ARQ_MORA.get(arq, 0.15)          # riesgo del arquetipo (0..0.40)
    w_tarjeta = 12 + 95 * r
    w_consumo = 50
    w_pyme = max(4, 42 - 75 * r)
    return [w_consumo, w_pyme, w_tarjeta]  # orden: Consumo, Pyme, Tarjeta

# Multiplicador de mora por REGIÓN (realismo geográfico: la capital muestra mejor
# comportamiento; el interior, más alto). El promedio ponderado por población es ~1.0
# para no mover la mora global, y como las regiones se reparten parejo entre bandas de
# score, la curva V1 no se distorsiona.
REGION_MORA_MULT = {
    "Metropolitana": 0.78,
    "Central":       0.88,
    "Suroccidente":  0.96,
    "Nororiente":    1.08,
    "Noroccidente":  1.12,
    "Suroriente":    1.16,
    "Norte":         1.20,
    "Petén":         1.28,
}

# ---------------------------------------------------------------------------
# Paso 1: asignar arquetipos y cohortes (barajado) -> lista de clientes base
# ---------------------------------------------------------------------------
def asignar_base():
    arqs = []
    for a, c in ARQ_CONTEOS.items():
        arqs.extend([a] * c)
    random.shuffle(arqs)

    # cohortes: reparto por peso
    cohorte_pool = []
    for coh in COHORTES:
        cohorte_pool.extend([coh] * round(COHORTE_PESO[coh] * N_CLIENTES))
    # ajustar longitud exacta
    while len(cohorte_pool) < N_CLIENTES:
        cohorte_pool.append(2025)
    cohorte_pool = cohorte_pool[:N_CLIENTES]
    random.shuffle(cohorte_pool)

    clientes = []
    for i in range(N_CLIENTES):
        clientes.append({"codigo_unico": f"CLI-{i+1:06d}",
                         "arquetipo": arqs[i],
                         "cohorte": cohorte_pool[i]})
    return clientes

# ---------------------------------------------------------------------------
# Paso 2: perfil demográfico + producto por cliente (según arquetipo)
# ---------------------------------------------------------------------------
def perfil_demografico(cli):
    arq = cli["arquetipo"]
    # producto
    if arq == "C7":
        producto = "Tarjeta de Crédito"
    elif arq in ("C5", "D2"):
        producto = "Crédito Pyme"
    elif arq in ("C4",):
        producto = "Crédito Consumo"
    elif arq == "C6":
        # C6 = deudores de riesgo medio sin seguro -> siempre crédito (tiene VERITAS/LSTM)
        producto = random.choices(["Crédito Consumo", "Crédito Pyme"], weights=[70, 30], k=1)[0]
    elif arq == "B4":
        # B4 = deteriorado silencioso -> LSTM > 65 => debe ser crédito (tiene proyección)
        producto = random.choices(["Crédito Consumo", "Crédito Pyme"], weights=[70, 30], k=1)[0]
    elif arq == "D4":
        producto = random.choice(["Crédito Pyme", "Crédito Consumo"])
    else:
        # producto sesgado por el riesgo del arquetipo (riesgoso -> tarjeta; sano -> pyme)
        producto = random.choices(
            ["Crédito Consumo", "Crédito Pyme", "Tarjeta de Crédito"],
            weights=_pesos_producto(arq), k=1)[0]

    # demografía
    if arq == "C4":
        estado_civil = "Soltero"
        edad = random.randint(18, 30)
        depto = random.choice(REGION_DEPTOS["Noroccidente"])
    else:
        estado_civil = random.choice(ESTADOS_CIVILES)
        edad = random.randint(18, 70)
        depto = elegir_departamento()
    region = DEPTO_REGION[depto]
    genero = random.choice(GENEROS)

    # monto / plazo
    if producto == "Tarjeta de Crédito":
        monto, plazo = None, None
    else:
        monto = monto_pyme() if producto == "Crédito Pyme" else monto_consumo()
        plazo = random.choice([12, 24, 36, 48, 60])

    fecha = fecha_en_cohorte(cli["cohorte"])

    cli.update(dict(genero=genero, edad=edad, departamento=depto, region=region,
                    estado_civil=estado_civil, tipo_producto=producto,
                    monto_credito=monto, plazo_meses=plazo,
                    fecha_originacion=fecha,
                    es_credito=(producto != "Tarjeta de Crédito")))
    return cli

# ---------------------------------------------------------------------------
# Paso 3: rasgos Verifiquemos (flags) + OSINT plan, según arquetipo
# Devuelve un dict de rasgos que alimenta score, veritas, comportamiento y LSTM.
# ---------------------------------------------------------------------------
def rasgos_verifiquemos(cli):
    arq = cli["arquetipo"]
    coh = cli["cohorte"]
    t = {
        # condiciones especiales
        "pep": False, "pep_representante": False, "pep_beneficiario_final": False,
        "contratista_estado": False, "ong": False, "fideicomiso": False,
        "entidad_no_lucrativa": False, "persona_obligada": False,
        # riesgo geográfico
        "transferencias_internacionales": False, "recibe_de_sancionados": False,
        "envia_a_sancionados": False,
        # listas
        "match_ofac": False, "match_onu": False, "match_engel": False,
        "match_cpe": False, "match_pep": False,
        # otros
        "mismatch_ingreso_actividad": False,
        # OSINT plan: 'neg'(adverse media), 'pos', 'none', 'neg_c2'(aparece en corrida2)
        "osint": "none",
        "osint_c2_extra": False,
    }
    naturaleza = "Persona Jurídica" if (cli["tipo_producto"] == "Crédito Pyme"
                                        and random.random() < 0.45) else "Persona Individual"
    categoria = "Nacional verificado en RENAP"
    actividad = random.choices(ACTIVIDADES, weights=ACTIVIDAD_PESOS, k=1)[0]
    perfil = random.choices(PERFILES_INGRESOS, weights=[18, 30, 28, 12, 8, 4], k=1)[0]
    prodserv = random.choices(PRODUCTOS_SERVICIO,
                              weights=[max(1, int(30 * (1 - PRODSERV_RIESGO[p])))
                                       for p in PRODUCTOS_SERVICIO], k=1)[0]
    facial = round(random.uniform(88, 99.5), 2)

    # ----- reglas por arquetipo -----
    if arq == "A1":  # bomba silenciosa: adverse media, mora ~18m
        t["osint"] = "neg"
    elif arq == "A2":  # fraude de identidad: facial bajo, default temprano
        facial = round(random.uniform(55, 84), 2)
    elif arq == "A3":  # incongruencia ingreso-actividad
        actividad = random.choice(["Estudiante", "Ama de casa"])
        perfil = random.choice(PERFIL_ALTO)
        t["mismatch_ingreso_actividad"] = True
    elif arq == "A4":  # PEP peligroso
        t["pep"] = True; t["match_pep"] = True; t["osint"] = "neg"
    elif arq == "A5":  # flujos sancionados
        actividad = random.choice(["Exportación/Importación", "Comercio en efectivo"])
        prodserv = "Compra/venta de divisas"
        t["transferencias_internacionales"] = True
        if random.random() < 0.6:
            t["recibe_de_sancionados"] = True
        if random.random() < 0.6:
            t["envia_a_sancionados"] = True
        if not (t["recibe_de_sancionados"] or t["envia_a_sancionados"]):
            t["recibe_de_sancionados"] = True
        t["osint"] = "neg"
    elif arq == "B1":  # hit nuevo en listas (aparece en corrida 2)
        t["osint_c2_extra"] = "lista"
    elif arq == "B2":  # se vuelve PEP en corrida 2
        t["osint_c2_extra"] = "pep"
    elif arq == "B3":  # adverse media nueva en corrida 2
        t["osint"] = "neg_c2"
    elif arq == "B4":  # deteriorado silencioso: corrida1 limpio y bajo, sube en 2
        t["osint_c2_extra"] = "signal"
    elif arq == "C1":  # sobreendeudado
        pass
    elif arq == "C2":  # cobro legal (siempre con señal adverse media)
        t["osint"] = "neg"
    elif arq == "C3":  # CPE flujo apretado
        t["contratista_estado"] = True; t["match_cpe"] = True
    elif arq == "C4":  # demográfico de riesgo (ya fijado en demografía)
        pass
    elif arq == "C5":  # dependencia concentrada (pyme)
        pass
    elif arq == "C6":  # riesgo medio sin seguro
        pass
    elif arq == "C7":  # revolvente atrapado (tarjeta)
        prodserv = "Tarjetas de crédito"
    elif arq == "D1":  # sano ejemplar
        facial = round(random.uniform(92.5, 99.9), 2)
        t["osint"] = "none"
    elif arq == "D2":  # empresario oculto: OSINT positivo revela actividad
        naturaleza = "Persona Individual"
        actividad = random.choice(["Comercio general", "Comercio en efectivo"])
        t["osint"] = "pos"
    elif arq == "D3":  # evolucionó bien (mejora en corrida 2)
        t["osint"] = "pos"
    elif arq == "D4":  # internacional legítimo
        categoria = random.choice(["Extranjero residente en Guatemala",
                                   "Extranjero no residente"])
        actividad = "Exportación/Importación"
        t["transferencias_internacionales"] = True
    elif arq == "E1":  # PEP inofensivo
        t["pep"] = True; t["match_pep"] = True; t["osint"] = "none"
    elif arq == "E2":  # promedio / neutro
        pass
    elif arq == "E3":  # buen pagador cerrado (cosechas antiguas)
        pass

    # condiciones especiales secundarias (poco frecuentes, coherentes)
    if naturaleza == "Persona Jurídica":
        if random.random() < 0.15:
            t["fideicomiso"] = True
        if random.random() < 0.10:
            t["pep_representante"] = True
    if actividad == "Organizaciones sin fines de lucro":
        t["ong"] = True; t["entidad_no_lucrativa"] = True
    if random.random() < 0.05:
        t["persona_obligada"] = True

    cli.update(dict(naturaleza=naturaleza, categoria_cliente=categoria,
                    actividad_economica=actividad, perfil_ingresos=perfil,
                    producto_servicio=prodserv, coincidencia_facial=facial))
    return t

# ---------------------------------------------------------------------------
# Paso 4: construir subfactores de score que SUMAN exactamente score_total
# ---------------------------------------------------------------------------
def construir_score(cli, t, corrida2=False):
    arq = cli["arquetipo"]
    # subfactores base a partir de flags
    s_id = 1
    for k in ("match_ofac", "match_onu", "match_engel"):
        if t[k]:
            s_id += 9
    if t["match_pep"]:
        s_id += 5
    if t["match_cpe"]:
        s_id += 4
    s_id = min(s_id, 30)

    s_geo = 1
    if t["recibe_de_sancionados"]:
        s_geo += 6
    if t["envia_a_sancionados"]:
        s_geo += 6
    if t["transferencias_internacionales"]:
        s_geo += 3
    s_geo = min(s_geo, 15)

    s_ing = 1 + (3 if t["mismatch_ingreso_actividad"] else 0)
    s_ing = min(s_ing, 5)

    s_act = min(15, 1 + round(14 * ACTIVIDAD_RIESGO.get(cli["actividad_economica"], 0.3)))

    s_cond = 0
    if t["pep"]:
        s_cond += 6
    if t["contratista_estado"]:
        s_cond += 4
    if t["fideicomiso"]:
        s_cond += 2
    if t["persona_obligada"]:
        s_cond += 2
    if t["ong"]:
        s_cond += 1
    s_cond = min(s_cond, 15)

    s_nat = 4 if cli["naturaleza"] == "Persona Jurídica" else 1

    s_ps = min(10, 1 + round(9 * PRODSERV_RIESGO.get(cli["producto_servicio"], 0.3)))

    subs = {"sub_identidad_listas": s_id, "sub_riesgo_geografico": s_geo,
            "sub_perfil_ingresos": s_ing, "sub_actividad_economica": s_act,
            "sub_condicion_especial": s_cond, "sub_naturaleza_cliente": s_nat,
            "sub_producto_servicio": s_ps}
    caps = {"sub_identidad_listas": 30, "sub_riesgo_geografico": 15,
            "sub_perfil_ingresos": 5, "sub_actividad_economica": 15,
            "sub_condicion_especial": 15, "sub_naturaleza_cliente": 10,
            "sub_producto_servicio": 10}

    # banda objetivo (con excepción de arquetipos que cambian en corrida 2)
    banda = ARQ_BANDA[arq]
    if arq == "E2":
        # E2 (masa neutra) se reparte ~75% Bajo / 25% Medio para poblar la banda Bajo
        banda = "Bajo" if random.random() < 0.75 else "Medio"
    if corrida2:
        if arq == "B4":
            banda = random.choice(["Medio", "Medio-alto"])   # sube
        elif arq == "D3":
            banda = "Bajo"                                     # mejora
        elif arq in ("B1", "B2", "B3"):
            banda = "Medio-alto"

    lo, hi = BAND_RANGE[banda]
    target = random.randint(lo, hi) + COHORTE_SCORE_OFFSET[cli["cohorte"]]
    # anclar la banda Bajo: el deterioro por cosecha no debe sacar a un cliente
    # "bajo/limpio" de la banda Bajo (clave para B4/D1 y para la curva V1)
    if banda == "Bajo" and not (corrida2 and arq in ("B4", "D3", "B1", "B2", "B3")):
        target = min(target, 29)
        if arq == "B4":
            target = min(target, 27)
    target = max(0, min(100, target))

    actual = sum(subs.values())
    diff = target - actual

    orden = ["sub_actividad_economica", "sub_producto_servicio", "sub_condicion_especial",
             "sub_riesgo_geografico", "sub_identidad_listas", "sub_naturaleza_cliente",
             "sub_perfil_ingresos"]
    if diff > 0:
        for k in orden:
            if diff <= 0:
                break
            headroom = caps[k] - subs[k]
            add = min(headroom, diff)
            subs[k] += add
            diff -= add
    elif diff < 0:
        need = -diff
        for k in orden:
            if need <= 0:
                break
            reducible = subs[k]
            take = min(reducible, need)
            subs[k] -= take
            need -= take

    total = sum(subs.values())
    total = max(0, min(100, total))
    banda_final = banda_de(total)
    subs["score_total"] = total
    subs["banda_score"] = banda_final
    subs["nivel_riesgo"] = nivel_de_banda(banda_final)
    subs["recomendacion"] = recomendacion_de_banda(banda_final)
    return subs

# ---------------------------------------------------------------------------
# Paso 5: comportamiento real (core) — coherente con arquetipo + banda (R1)
# ---------------------------------------------------------------------------
def generar_comportamiento(cli, t, banda1):
    arq = cli["arquetipo"]
    # mora del arquetipo, modulada por la región (gradiente geográfico realista)
    mora_base = ARQ_MORA[arq] * REGION_MORA_MULT.get(cli["region"], 1.0)
    mora_base = min(0.95, mora_base)

    # arquetipos con mora forzada / imposible
    if arq in ("D1", "E3", "B4"):
        en_mora = False
    elif arq == "C2":
        en_mora = True
    else:
        en_mora = random.random() < mora_base

    tuvo_atrasos = False
    cantidad = None
    termino_de_pagar = True
    termino_a_tiempo = True
    cobro_legal = False
    meses_hasta_mora = None
    alerta_aml = False
    seguro = random.random() < 0.90

    monto = cli["monto_credito"]
    saldo = None

    if en_mora:
        tuvo_atrasos = True
        termino_de_pagar = False
        termino_a_tiempo = None
        # cantidad de atrasos por arquetipo
        if arq == "C1":
            cantidad = random.randint(5, 10)
        elif arq in ("C2",):
            cantidad = random.randint(4, 10)
        elif arq in ("C5", "C7"):
            cantidad = random.randint(2, 6)
        elif arq in ("A1", "A3", "A4", "A5", "C4"):
            cantidad = random.randint(2, 8)
        else:
            cantidad = random.randint(1, 6)
        # meses hasta mora
        if arq == "A2":
            meses_hasta_mora = random.randint(1, 5)     # default temprano
        elif arq == "A1":
            meses_hasta_mora = random.randint(14, 22)   # ~18 meses
        else:
            meses_hasta_mora = random.randint(3, 30)
        if arq == "C2" or (arq in ("A2", "C1") and random.random() < 0.5):
            cobro_legal = True
        if arq in ("A1", "A4", "A5"):
            alerta_aml = True
        elif t["recibe_de_sancionados"] or t["envia_a_sancionados"]:
            alerta_aml = random.random() < 0.7
        if monto is not None:
            saldo = round(monto * random.uniform(0.35, 0.95), 2)
    else:
        # sin mora: puede haber atrasos leves y recuperación
        if arq in ("C3",):          # atrasos cíclicos pero termina pagando
            tuvo_atrasos = True
            cantidad = random.randint(2, 4)
            termino_de_pagar = True
            termino_a_tiempo = False
        elif arq in ("C6",):        # 1-3 atrasos, aún pagando
            tuvo_atrasos = True
            cantidad = random.randint(1, 3)
            termino_de_pagar = random.random() < 0.4
            termino_a_tiempo = False if termino_de_pagar else None
        elif arq == "C7":           # tarjeta con atrasos crecientes
            tuvo_atrasos = True
            cantidad = random.randint(1, 5)
            termino_de_pagar = False
            termino_a_tiempo = None
        elif arq in ("D1", "E3"):   # impecables
            tuvo_atrasos = False
            termino_de_pagar = True
            termino_a_tiempo = True
        elif arq in ("D2", "D3", "D4"):
            tuvo_atrasos = random.random() < 0.15
            if tuvo_atrasos:
                cantidad = random.randint(1, 2)
            termino_de_pagar = True
            termino_a_tiempo = True
        elif arq == "E2":
            tuvo_atrasos = random.random() < 0.35
            if tuvo_atrasos:
                cantidad = random.randint(1, 2)
            termino_de_pagar = random.random() < 0.7
            termino_a_tiempo = (random.random() < 0.7) if termino_de_pagar else None
        elif arq == "B4":
            tuvo_atrasos = False
            termino_de_pagar = False   # crédito vigente
            termino_a_tiempo = None
        elif arq in ("B1", "B2", "B3"):
            tuvo_atrasos = random.random() < 0.2
            if tuvo_atrasos:
                cantidad = random.randint(1, 3)
            termino_de_pagar = False   # crédito vigente
            termino_a_tiempo = None
        else:
            tuvo_atrasos = random.random() < 0.2
            if tuvo_atrasos:
                cantidad = random.randint(1, 3)
            termino_de_pagar = random.random() < 0.6
            termino_a_tiempo = (random.random() < 0.8) if termino_de_pagar else None

    # C6 explícitamente SIN seguro (escenario de colocación)
    if arq == "C6":
        seguro = False
    elif arq in ("D1", "E3", "D2", "D4"):
        seguro = random.random() < 0.92

    # saldo expuesto por defecto (aunque no esté en mora, para créditos vigentes)
    if saldo is None and monto is not None and not termino_de_pagar:
        saldo = round(monto * random.uniform(0.2, 0.8), 2)

    comp = dict(
        codigo_unico=cli["codigo_unico"], tuvo_atrasos=tuvo_atrasos,
        cantidad_atrasos=cantidad, termino_de_pagar=termino_de_pagar,
        termino_a_tiempo=termino_a_tiempo, cobro_legal=cobro_legal,
        tiene_seguro_vida_credito=seguro, en_mora=en_mora,
        meses_hasta_mora=meses_hasta_mora, alerta_aml=alerta_aml,
        saldo_expuesto=saldo,
    )
    return comp

# ---------------------------------------------------------------------------
# Paso 6: VERITAS (solo créditos) — coherente con arquetipo/comportamiento
# ---------------------------------------------------------------------------
def generar_veritas(cli, t, comp):
    arq = cli["arquetipo"]
    # comportamiento_pago
    if arq in ("C1", "C2"):
        comp_pago = "C"
    elif arq in ("A1", "A2", "A3", "A5", "C4"):
        comp_pago = random.choice(["B", "C"])
    elif arq in ("D1", "E3", "D3", "D4", "D2"):
        comp_pago = "A"
    elif arq in ("C6", "E2", "B4", "C3", "C5"):
        comp_pago = "B"
    elif arq == "E1":
        comp_pago = random.choice(["A", "B"])
    else:
        comp_pago = random.choice(["A", "B", "B", "C"])
    # coherencia con mora real
    if comp["en_mora"] and comp_pago == "A":
        comp_pago = "B"
    if not comp["en_mora"] and arq in ("D1", "E3") :
        comp_pago = "A"

    # capacidad de pago (ratio)
    if arq in ("C1",):
        ratio = round(random.uniform(0.55, 0.98), 2)
    elif arq in ("C2", "A3"):
        ratio = round(random.uniform(0.6, 1.05), 2)
    elif arq in ("D1", "D4", "E3"):
        ratio = round(random.uniform(1.25, 2.8), 2)
    elif comp_pago == "C":
        ratio = round(random.uniform(0.7, 1.05), 2)
    elif comp_pago == "A":
        ratio = round(random.uniform(1.2, 2.6), 2)
    else:
        ratio = round(random.uniform(1.0, 1.25), 2)
    if ratio > 1.20 and ratio < 3:
        capacidad = "A"
    elif ratio >= 1.0:
        capacidad = "B"
    else:
        capacidad = "C"

    # dependencia de clientes
    if arq in ("C3", "C5"):
        dependencia = round(random.uniform(70.5, 95), 2)
    elif arq in ("D1", "E3"):
        dependencia = round(random.uniform(5, 45), 2)
    else:
        dependencia = round(random.uniform(10, 80), 2)

    # scoring crediticio (30-100, mayor = mejor)
    if arq in ("D1", "E3"):
        scoring = random.randint(82, 100)
    elif comp_pago == "C":
        scoring = random.randint(30, 55)
    elif comp_pago == "A":
        scoring = random.randint(72, 98)
    else:
        scoring = random.randint(50, 78)

    return dict(codigo_unico=cli["codigo_unico"], scoring_crediticio=scoring,
                comportamiento_pago=comp_pago, dependencia_clientes=dependencia,
                capacidad_pago=capacidad, ratio_capacidad=ratio), comp_pago, capacidad

# ---------------------------------------------------------------------------
# Paso 7: OSINT — hallazgos por corrida coherentes con el arquetipo
# ---------------------------------------------------------------------------
FUENTES_NEG = ["Portal de noticias", "Diario nacional", "Registro judicial",
               "Boletín criminal", "Red social", "Lista de riesgo"]
FUENTES_POS = ["Directorio empresarial", "Cámara de comercio", "Portal de proveedores",
               "Perfil profesional", "Nota de prensa"]

def generar_osint(cli, t):
    arq = cli["arquetipo"]
    filas = []
    coh = cli["cohorte"]
    mult = COHORTE_ADVERSE_MULT[coh]

    def add(corrida, categoria, sentimiento, nivel, fuente, comentario):
        filas.append(dict(codigo_unico=cli["codigo_unico"], numero_corrida=corrida,
                          fuente=fuente, categoria=categoria, sentimiento=sentimiento,
                          nivel_riesgo=nivel, comentario=comentario))

    if t["osint"] == "neg":
        n = random.randint(1, 3)
        for _ in range(n):
            cat = random.choice(["Criminal", "Noticias", "Listas"])
            nivel = random.choice(["Medio", "Alto"])
            add(1, cat, "Negativo", nivel, random.choice(FUENTES_NEG),
                "Mención adversa detectada en fuentes abiertas.")
            add(2, cat, "Negativo", nivel, random.choice(FUENTES_NEG),
                "Mención adversa persistente.")
    elif t["osint"] == "neg_c2":   # B3: limpio en 1, adverse media en 2
        add(1, "General", "Neutral", "Sin riesgo", random.choice(FUENTES_POS),
            "Sin hallazgos relevantes en la primera corrida.")
        n = random.randint(1, 2)
        for _ in range(n):
            cat = random.choice(["Criminal", "Noticias"])
            add(2, cat, "Negativo", random.choice(["Medio", "Alto"]),
                random.choice(FUENTES_NEG), "Nueva mención adversa (monitoreo).")
    elif t["osint"] == "pos":
        add(1, "General", random.choice(["Positivo", "Neutral"]), "Sin riesgo",
            random.choice(FUENTES_POS), "Actividad comercial verificable.")
        add(2, "General", random.choice(["Positivo", "Neutral"]), "Sin riesgo",
            random.choice(FUENTES_POS), "Actividad comercial verificable.")
    else:  # none: a veces un hallazgo neutro
        if random.random() < 0.25:
            add(1, "General", "Neutral", "Sin riesgo", random.choice(FUENTES_POS),
                "Presencia pública sin señales de riesgo.")
            add(2, "General", "Neutral", "Sin riesgo", random.choice(FUENTES_POS),
                "Presencia pública sin señales de riesgo.")

    # extra por deltas de corrida 2
    if t["osint_c2_extra"] == "signal":   # B4
        add(2, "Noticias", "Negativo", "Medio", random.choice(FUENTES_NEG),
            "Señal de deterioro detectada en monitoreo.")
    elif t["osint_c2_extra"] == "lista":  # B1
        add(2, "Listas", "Negativo", "Alto", "Lista de riesgo",
            "Coincidencia nueva en listas de sanción.")
    elif t["osint_c2_extra"] == "pep":    # B2
        add(2, "Noticias", "Neutral", "Medio", random.choice(FUENTES_NEG),
            "Cliente identificado como PEP en monitoreo.")

    # R2: adverse media adicional en cosechas recientes (narrativa "2.3x más flags")
    # sprinkle ligero para no diluir el contraste de V2
    if arq in ("E2", "C6", "C4", "A3") and t["osint"] == "none":
        if random.random() < 0.02 * mult:
            add(1, "Noticias", "Negativo", "Medio", random.choice(FUENTES_NEG),
                "Mención adversa en fuentes abiertas.")
            add(2, "Noticias", "Negativo", "Medio", random.choice(FUENTES_NEG),
                "Mención adversa en fuentes abiertas.")
            cli["_adverse_extra"] = True
    return filas

# ---------------------------------------------------------------------------
# Paso 8: LSTM (R5) — probabilidad de mora como función del resto
# ---------------------------------------------------------------------------
def calcular_lstm(cli, t, comp, veritas, banda1, banda2, tiene_adverse):
    arq = cli["arquetipo"]
    contribs = {}

    # atrasos previos
    if comp["cantidad_atrasos"]:
        contribs["atrasos_previos"] = min(30, comp["cantidad_atrasos"] * 4.0)
    # capacidad de pago VERITAS
    if veritas:
        cap = veritas["capacidad_pago"]
        contribs["capacidad_pago_veritas"] = {"C": 25.0, "B": 8.0, "A": -15.0}[cap]
        comportp = veritas["comportamiento_pago"]
        contribs["comportamiento_veritas"] = {"C": 15.0, "B": 0.0, "A": -10.0}[comportp]
        if veritas["dependencia_clientes"] > 70:
            contribs["sobreendeudamiento"] = 8.0
    # score verifiquemos (banda de originación)
    contribs["score_verifiquemos"] = {"Bajo": -8.0, "Medio": 4.0,
                                       "Medio-alto": 12.0, "Alto": 20.0}[banda1]
    # adverse media
    if tiene_adverse:
        contribs["adverse_media"] = 18.0
    # deriva de score entre corridas (B4 y monitoreo)
    orden = ["Bajo", "Medio", "Medio-alto", "Alto"]
    delta = orden.index(banda2) - orden.index(banda1)
    if delta > 0:
        contribs["deriva_score"] = 18.0 * delta
    # cobro legal previo
    if comp["cobro_legal"]:
        contribs["cobro_legal_previo"] = 15.0
    # condición PEP/CPE
    if t["pep"] or t["contratista_estado"] or t["match_pep"] or t["match_cpe"]:
        contribs["condicion_pep_cpe"] = 5.0
    # riesgo geográfico de fondos
    if t["recibe_de_sancionados"] or t["envia_a_sancionados"]:
        contribs["riesgo_geografico_fondos"] = 12.0
    # perfil demográfico (soltero joven en Noroccidente)
    if (cli["estado_civil"] == "Soltero" and cli["edad"] <= 30
            and cli["region"] == "Noroccidente"):
        contribs["perfil_demografico"] = 10.0
    # edad extrema
    if cli["edad"] < 23 or cli["edad"] > 65:
        contribs["edad"] = 4.0

    base = 12.0
    prob = base + sum(contribs.values()) + random.uniform(-5, 5)

    # ----- reglas duras -----
    if arq == "D1":
        prob = min(prob, random.uniform(3, 12))
    elif arq == "C1":
        prob = max(prob, random.uniform(55, 75))
    elif arq == "B4":
        prob = max(prob, random.uniform(66, 85))       # deteriorado silencioso
        contribs["deriva_score"] = contribs.get("deriva_score", 0) + 20
    elif arq == "E1":
        prob = min(prob, random.uniform(8, 22))
    elif arq in ("D2", "D3", "D4", "E3"):
        prob = min(prob, random.uniform(6, 20))
    elif arq == "C6":
        # riesgo MEDIO por definición: anclar en 34-58 (nivel_riesgo = Medio) para V9
        prob = max(prob, random.uniform(34, 42))
        prob = min(prob, 58)

    prob = max(0.0, min(100.0, prob))
    prob = round(prob, 2)

    # factores explicativos: los de mayor contribución positiva realmente presentes
    positivos = {k: v for k, v in contribs.items() if v > 0}
    if positivos:
        top = sorted(positivos.items(), key=lambda kv: kv[1], reverse=True)
        hi = min(4, len(top))
        k_top = random.randint(2, hi) if hi >= 2 else 1
        factores = [k for k, _ in top[:k_top]]
    else:
        # cliente sano: usar factores demográficos/geográficos benignos presentes
        factores = []
        factores.append("edad")
        factores.append("estado_civil" if cli["estado_civil"] != "Soltero" else "region")
    if len(factores) < 2:
        factores.append("region")
    factores = factores[:4]

    return dict(codigo_unico=cli["codigo_unico"], probabilidad_mora=prob,
                horizonte_meses=12, nivel_riesgo=nivel_lstm(prob),
                factores_explicativos=json.dumps(factores, ensure_ascii=False))

# ---------------------------------------------------------------------------
# Ensamble de una fila de validacion
# ---------------------------------------------------------------------------
VAL_COLS = [
    "codigo_unico", "numero_corrida", "fecha_corrida", "naturaleza",
    "categoria_cliente", "actividad_economica", "perfil_ingresos", "producto_servicio",
    "pep", "pep_representante", "pep_beneficiario_final", "contratista_estado", "ong",
    "fideicomiso", "entidad_no_lucrativa", "persona_obligada",
    "transferencias_internacionales", "recibe_de_sancionados", "envia_a_sancionados",
    "match_ofac", "match_onu", "match_engel", "match_cpe", "match_pep",
    "coincidencia_facial", "mismatch_ingreso_actividad",
    "sub_identidad_listas", "sub_riesgo_geografico", "sub_perfil_ingresos",
    "sub_actividad_economica", "sub_condicion_especial", "sub_naturaleza_cliente",
    "sub_producto_servicio", "score_total", "banda_score", "nivel_riesgo",
    "recomendacion",
]

def fila_validacion(cli, t, subs, corrida, fecha):
    d = dict(codigo_unico=cli["codigo_unico"], numero_corrida=corrida, fecha_corrida=fecha,
             naturaleza=cli["naturaleza"], categoria_cliente=cli["categoria_cliente"],
             actividad_economica=cli["actividad_economica"],
             perfil_ingresos=cli["perfil_ingresos"],
             producto_servicio=cli["producto_servicio"],
             coincidencia_facial=cli["coincidencia_facial"])
    for k in ("pep", "pep_representante", "pep_beneficiario_final", "contratista_estado",
              "ong", "fideicomiso", "entidad_no_lucrativa", "persona_obligada",
              "transferencias_internacionales", "recibe_de_sancionados",
              "envia_a_sancionados", "match_ofac", "match_onu", "match_engel",
              "match_cpe", "match_pep", "mismatch_ingreso_actividad"):
        d[k] = t[k]
    d.update(subs)
    return [d[c] for c in VAL_COLS]

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print(f"[1/9] Asignando arquetipos y cohortes (seed={SEED}) ...")
    clientes = asignar_base()

    print("[2/9] Perfil demográfico + producto ...")
    for cli in clientes:
        perfil_demografico(cli)

    print("[3/9] Rasgos Verifiquemos por cliente ...")
    rasgos = {}
    for cli in clientes:
        rasgos[cli["codigo_unico"]] = rasgos_verifiquemos(cli)

    # --- Overlay PEP para cumplir R3 (crecimiento PEP con crédito por cohorte) ---
    print("[3b/9] Overlay PEP con crédito por cohorte (R3) ...")
    # candidatos benignos con crédito, no-PEP aún
    # (D1 se excluye para preservar "5 listas limpias" del sano ejemplar)
    benignos = ("E2", "E3", "D2", "D4", "C6")
    pep_base_por_coh = {c: 0 for c in COHORTES}
    for cli in clientes:
        t = rasgos[cli["codigo_unico"]]
        if t["pep"] and cli["es_credito"]:
            pep_base_por_coh[cli["cohorte"]] += 1
    for coh in COHORTES:
        faltan = PEP_CREDITO_OBJETIVO[coh] - pep_base_por_coh[coh]
        if faltan <= 0:
            continue
        candidatos = [cli for cli in clientes
                      if cli["cohorte"] == coh and cli["es_credito"]
                      and cli["arquetipo"] in benignos
                      and not rasgos[cli["codigo_unico"]]["pep"]]
        random.shuffle(candidatos)
        for cli in candidatos[:faltan]:
            t = rasgos[cli["codigo_unico"]]
            t["pep"] = True
            t["match_pep"] = True

    print("[4/9] Score corrida 1 y 2 ...")
    val_rows = []
    subs1_por_cli = {}
    banda_por_cli = {}
    for cli in clientes:
        t = rasgos[cli["codigo_unico"]]
        subs1 = construir_score(cli, t, corrida2=False)
        subs1_por_cli[cli["codigo_unico"]] = subs1
        banda_por_cli[cli["codigo_unico"]] = subs1["banda_score"]

        # corrida 2: por defecto igual; deltas para B1-B4 y D3
        arq = cli["arquetipo"]
        t2 = dict(t)  # copia de flags para posibles cambios en corrida 2
        if arq == "B1":
            if random.random() < 0.5:
                t2["match_ofac"] = True
            else:
                t2["match_onu"] = True
        elif arq == "B2":
            t2["pep"] = True
            t2["match_pep"] = True

        if arq in ("B1", "B2", "B3", "B4", "D3"):
            subs2 = construir_score(cli, t2, corrida2=True)
        else:
            # variación mínima: reusar subs1 con leve ruido en score manteniendo suma
            subs2 = dict(subs1)
        banda2 = subs2["banda_score"]
        cli["_banda2"] = banda2
        cli["_t2"] = t2

        val_rows.append(fila_validacion(cli, t, subs1, 1, cli["fecha_originacion"]))
        val_rows.append(fila_validacion(cli, t2, subs2, 2, CORRIDA2_FECHA))

    print("[5/9] Comportamiento (core) ...")
    comp_por_cli = {}
    for cli in clientes:
        t = rasgos[cli["codigo_unico"]]
        comp = generar_comportamiento(cli, t, banda_por_cli[cli["codigo_unico"]])
        comp_por_cli[cli["codigo_unico"]] = comp

    print("[6/9] VERITAS (solo créditos) ...")
    veritas_rows = []
    veritas_por_cli = {}
    for cli in clientes:
        if not cli["es_credito"]:
            continue
        t = rasgos[cli["codigo_unico"]]
        vfila, _, _ = generar_veritas(cli, t, comp_por_cli[cli["codigo_unico"]])
        veritas_por_cli[cli["codigo_unico"]] = vfila
        veritas_rows.append(vfila)

    print("[7/9] OSINT ...")
    osint_rows = []
    adverse_por_cli = {}
    for cli in clientes:
        t = rasgos[cli["codigo_unico"]]
        filas = generar_osint(cli, t)
        osint_rows.extend(filas)
        adverse_por_cli[cli["codigo_unico"]] = any(
            f["sentimiento"] == "Negativo" and f["categoria"] in ("Criminal", "Noticias", "Listas")
            for f in filas)

    print("[8/9] Proyección LSTM (R5) ...")
    proy_rows = []
    for cli in clientes:
        if not cli["es_credito"]:
            continue
        t = rasgos[cli["codigo_unico"]]
        comp = comp_por_cli[cli["codigo_unico"]]
        veritas = veritas_por_cli.get(cli["codigo_unico"])
        proy = calcular_lstm(cli, t, comp, veritas,
                             banda_por_cli[cli["codigo_unico"]],
                             cli["_banda2"], adverse_por_cli[cli["codigo_unico"]])
        proy_rows.append(proy)

    # -----------------------------------------------------------------------
    # Inserción con COPY
    # -----------------------------------------------------------------------
    print("[9/9] Insertando en PostgreSQL (COPY) ...")
    with _connect() as conn:
        with conn.cursor() as cur:
            # aplicar el esquema (DROP + CREATE, idempotente): funciona tanto en una
            # base nueva (Neon en la nube) como en una existente (local)
            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
            with open(schema_path, "r", encoding="utf-8") as _fh:
                cur.execute(_fh.read())

            # solicitante
            with cur.copy(
                "COPY solicitante (codigo_unico, genero, edad, departamento, region, "
                "estado_civil, tipo_producto, monto_credito, plazo_meses, "
                "fecha_originacion, cohorte, arquetipo) FROM STDIN") as cp:
                for cli in clientes:
                    cp.write_row([
                        cli["codigo_unico"], cli["genero"], cli["edad"],
                        cli["departamento"], cli["region"], cli["estado_civil"],
                        cli["tipo_producto"], cli["monto_credito"], cli["plazo_meses"],
                        cli["fecha_originacion"], cli["cohorte"], cli["arquetipo"]])

            # validacion
            cols = ", ".join(VAL_COLS)
            with cur.copy(f"COPY validacion ({cols}) FROM STDIN") as cp:
                for row in val_rows:
                    cp.write_row(row)

            # osint
            with cur.copy(
                "COPY osint_hallazgo (codigo_unico, numero_corrida, fuente, categoria, "
                "sentimiento, nivel_riesgo, comentario) FROM STDIN") as cp:
                for f in osint_rows:
                    cp.write_row([f["codigo_unico"], f["numero_corrida"], f["fuente"],
                                  f["categoria"], f["sentimiento"], f["nivel_riesgo"],
                                  f["comentario"]])

            # veritas
            with cur.copy(
                "COPY veritas (codigo_unico, scoring_crediticio, comportamiento_pago, "
                "dependencia_clientes, capacidad_pago, ratio_capacidad) FROM STDIN") as cp:
                for v in veritas_rows:
                    cp.write_row([v["codigo_unico"], v["scoring_crediticio"],
                                  v["comportamiento_pago"], v["dependencia_clientes"],
                                  v["capacidad_pago"], v["ratio_capacidad"]])

            # comportamiento
            with cur.copy(
                "COPY comportamiento (codigo_unico, tuvo_atrasos, cantidad_atrasos, "
                "termino_de_pagar, termino_a_tiempo, cobro_legal, tiene_seguro_vida_credito, "
                "en_mora, meses_hasta_mora, alerta_aml, saldo_expuesto) FROM STDIN") as cp:
                for c in [comp_por_cli[cli["codigo_unico"]] for cli in clientes]:
                    cp.write_row([c["codigo_unico"], c["tuvo_atrasos"], c["cantidad_atrasos"],
                                  c["termino_de_pagar"], c["termino_a_tiempo"], c["cobro_legal"],
                                  c["tiene_seguro_vida_credito"], c["en_mora"],
                                  c["meses_hasta_mora"], c["alerta_aml"], c["saldo_expuesto"]])

            # proyeccion_mora
            with cur.copy(
                "COPY proyeccion_mora (codigo_unico, probabilidad_mora, horizonte_meses, "
                "nivel_riesgo, factores_explicativos) FROM STDIN") as cp:
                for p in proy_rows:
                    cp.write_row([p["codigo_unico"], p["probabilidad_mora"],
                                  p["horizonte_meses"], p["nivel_riesgo"],
                                  p["factores_explicativos"]])
        conn.commit()

    print("\n== Resumen ==")
    print(f"  solicitantes : {len(clientes):>7}")
    print(f"  validaciones : {len(val_rows):>7}")
    print(f"  osint        : {len(osint_rows):>7}")
    print(f"  veritas      : {len(veritas_rows):>7}")
    print(f"  proyecciones : {len(proy_rows):>7}")
    print("Listo.")

if __name__ == "__main__":
    main()
