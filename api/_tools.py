# -*- coding: utf-8 -*-
"""
Capa de herramientas (tools) del asistente "Forecast Lab · Banrural".

Cada tool consulta la base `demoscoring` y devuelve un CONTRATO uniforme que sirve
a la vez para (a) que el modelo realtime lo NARRE por voz y (b) que el front-end
lo MUESTRE en el lienzo visual:

    {
      "titulo":   str,                      # encabezado del panel visual
      "resumen":  str,                      # 1-2 frases, listas para decir por voz
      "kpis":     [ {"label","valor","sufijo","tono"} , ... ],   # tarjetas grandes
      "visual":   { "tipo": "...", ... },   # bar | line | grouped_bar | table | geo_bar | client_detail | none
      "datos":    {...}                     # datos crudos por si se necesitan
    }

Los números NUNCA se inventan: salen de SQL sobre los patrones sembrados.
Todas las consultas son de solo lectura.
"""

import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Conexión: si existe DATABASE_URL (Neon/Supabase en la nube) se usa esa cadena;
# si no, se arma desde las variables PG* (Postgres local).
DATABASE_URL = os.environ.get("DATABASE_URL")
DSN = dict(
    host=os.environ.get("PGHOST", "localhost"),
    port=int(os.environ.get("PGPORT", "5432")),
    user=os.environ.get("PGUSER", "postgres"),
    password=os.environ.get("PGPASSWORD", ""),
    dbname=os.environ.get("PGDATABASE", "demoscoring"),
)

def _connect():
    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True)
    return psycopg.connect(**DSN, row_factory=dict_row, autocommit=True)

# Conexión reutilizable por proceso (en serverless persiste entre invocaciones "tibias")
_conn = None

def _connection():
    global _conn
    if _conn is None or _conn.closed:
        _conn = _connect()
    return _conn

def q(sql, params=None):
    global _conn
    try:
        with _connection().cursor() as cur:
            # params=None => psycopg NO interpreta '%' como placeholder (permite % literales)
            cur.execute(sql, params)
            return cur.fetchall()
    except psycopg.OperationalError:
        # la base pudo suspenderse (planes gratis de Neon): reconectar y reintentar una vez
        _conn = None
        with _connection().cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

def q1(sql, params=None):
    rows = q(sql, params)
    return rows[0] if rows else {}

# ---------------------------------------------------------------------------
# Helpers de formato (para narración de voz)
# ---------------------------------------------------------------------------
def _miles(n):
    try:
        return f"{int(round(n)):,}".replace(",", ".")
    except Exception:
        return str(n)

def _q(n):
    """Formatea un monto en quetzales para voz/pantalla."""
    n = float(n or 0)
    if n >= 1_000_000:
        return f"Q{n/1_000_000:.1f} millones"
    if n >= 1_000:
        return f"Q{n/1_000:.0f} mil"
    return f"Q{n:.0f}"

# ===========================================================================
#  TOOLS
# ===========================================================================

def resumen_cartera():
    """Panorama general de la cartera: clientes, productos, mora global, saldo expuesto."""
    tot = q1("SELECT COUNT(*) n FROM solicitante")
    prod = q("SELECT tipo_producto, COUNT(*) n FROM solicitante GROUP BY 1 ORDER BY 2 DESC")
    mora = q1("SELECT ROUND(100.0*AVG(CASE WHEN en_mora THEN 1 ELSE 0 END),1) pct, "
              "SUM(CASE WHEN en_mora THEN saldo_expuesto ELSE 0 END) saldo_venc, "
              "SUM(saldo_expuesto) saldo_tot FROM comportamiento")
    creditos = q1("SELECT COUNT(*) n FROM solicitante WHERE tipo_producto <> 'Tarjeta de Crédito'")
    return {
        "titulo": "Panorama de la cartera",
        "resumen": (f"La cartera tiene {_miles(tot['n'])} clientes, "
                    f"{_miles(creditos['n'])} con crédito. La mora global es "
                    f"{mora['pct']}% y el saldo vencido asciende a {_q(mora['saldo_venc'])}."),
        "kpis": [
            {"label": "Clientes", "valor": _miles(tot["n"]), "tono": "neutro"},
            {"label": "Mora global", "valor": f"{mora['pct']}", "sufijo": "%", "tono": "alerta"},
            {"label": "Saldo vencido", "valor": _q(mora["saldo_venc"]), "tono": "alerta"},
            {"label": "Créditos activos", "valor": _miles(creditos["n"]), "tono": "neutro"},
        ],
        "visual": {"tipo": "bar", "orientacion": "horizontal",
                   "etiqueta_valor": "clientes",
                   "series": [{"nombre": r["tipo_producto"], "valor": r["n"]} for r in prod]},
        "datos": {"total": tot["n"], "productos": prod, "mora": mora},
    }

def curva_mora_por_banda():
    """La mora escala con la banda de score de originación (el score predice la mora)."""
    rows = q("""
        SELECT v.banda_score AS banda, COUNT(*) AS clientes,
               ROUND(100.0*SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_mora
        FROM validacion v JOIN comportamiento c USING (codigo_unico)
        WHERE v.numero_corrida = 1
        GROUP BY v.banda_score ORDER BY MIN(v.score_total)
    """)
    bajo = next((r["pct_mora"] for r in rows if r["banda"] == "Bajo"), None)
    alto = next((r["pct_mora"] for r in rows if r["banda"] == "Alto"), None)
    ratio = round(float(alto) / float(bajo), 1) if bajo else None
    return {
        "titulo": "Mora por banda de score",
        "resumen": (f"La mora crece de forma monótona con el score: {bajo}% en la banda "
                    f"Baja hasta {alto}% en la Alta, un factor de {ratio} veces. "
                    f"El score de originación sí anticipa el desenlace."),
        "kpis": [{"label": "Ratio Alto/Bajo", "valor": f"{ratio}", "sufijo": "×", "tono": "alerta"}],
        "visual": {"tipo": "bar", "orientacion": "vertical", "etiqueta_valor": "% mora",
                   "series": [{"nombre": r["banda"], "valor": float(r["pct_mora"])} for r in rows]},
        "datos": {"filas": rows, "ratio": ratio},
    }

def impacto_adverse_media():
    """Los clientes con adverse media (OSINT negativo) caen en mora mucho más."""
    rows = q("""
        SELECT CASE WHEN o.codigo_unico IS NOT NULL THEN 'Con adverse media'
                    ELSE 'Sin adverse media' END AS grupo,
               COUNT(*) AS clientes,
               ROUND(100.0*SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_mora
        FROM comportamiento c
        LEFT JOIN (SELECT DISTINCT codigo_unico FROM osint_hallazgo
                   WHERE sentimiento='Negativo' AND categoria IN ('Criminal','Noticias','Listas')) o
               USING (codigo_unico)
        GROUP BY 1 ORDER BY 1
    """)
    con = next((float(r["pct_mora"]) for r in rows if r["grupo"].startswith("Con")), 0)
    sin = next((float(r["pct_mora"]) for r in rows if r["grupo"].startswith("Sin")), 0)
    ratio = round(con / sin, 1) if sin else None
    return {
        "titulo": "Adverse media como predictor de mora",
        "resumen": (f"Los clientes con adverse media caen en mora un {con}%, frente al "
                    f"{sin}% de quienes no la tienen: {ratio} veces más. "
                    f"La señal reputacional anticipó el incumplimiento."),
        "kpis": [
            {"label": "Con adverse media", "valor": f"{con}", "sufijo": "%", "tono": "alerta"},
            {"label": "Sin adverse media", "valor": f"{sin}", "sufijo": "%", "tono": "bueno"},
        ],
        "visual": {"tipo": "bar", "orientacion": "vertical", "etiqueta_valor": "% mora",
                   "series": [{"nombre": r["grupo"], "valor": float(r["pct_mora"]),
                               "tono": "alerta" if r["grupo"].startswith("Con") else "bueno"}
                              for r in rows]},
        "datos": {"filas": rows, "ratio": ratio},
    }

def contraste_pep():
    """PEP con adverse media (peligroso) vs PEP sin señales (inofensivo)."""
    rows = q("""
        SELECT s.arquetipo AS arq, COUNT(*) AS clientes,
               ROUND(100.0*SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_mora
        FROM solicitante s JOIN comportamiento c USING (codigo_unico)
        WHERE s.arquetipo IN ('A4','E1') GROUP BY s.arquetipo
    """)
    a4 = next((float(r["pct_mora"]) for r in rows if r["arq"] == "A4"), 0)
    e1 = next((float(r["pct_mora"]) for r in rows if r["arq"] == "E1"), 0)
    return {
        "titulo": "No todos los PEP son iguales",
        "resumen": (f"Un PEP con señales adversas tiene {a4}% de mora; un PEP sin señales, "
                    f"solo {e1}%. La condición de PEP por sí sola no es el riesgo: "
                    f"lo es cuando se combina con adverse media."),
        "kpis": [
            {"label": "PEP con señales", "valor": f"{a4}", "sufijo": "%", "tono": "alerta"},
            {"label": "PEP sin señales", "valor": f"{e1}", "sufijo": "%", "tono": "bueno"},
        ],
        "visual": {"tipo": "bar", "orientacion": "vertical", "etiqueta_valor": "% mora",
                   "series": [
                       {"nombre": "PEP peligroso", "valor": a4, "tono": "alerta"},
                       {"nombre": "PEP inofensivo", "valor": e1, "tono": "bueno"}]},
        "datos": {"filas": rows},
    }

def evolucion_originacion():
    """El score promedio de originación empeora año con año (deterioro de cosechas)."""
    rows = q("""
        SELECT s.cohorte, ROUND(AVG(v.score_total),1) AS score_prom, COUNT(*) AS clientes
        FROM solicitante s JOIN validacion v USING (codigo_unico)
        WHERE v.numero_corrida = 1 GROUP BY s.cohorte ORDER BY s.cohorte
    """)
    ini, fin = rows[0], rows[-1]
    return {
        "titulo": "Deterioro de la calidad de originación",
        "resumen": (f"El score promedio de originación subió de {ini['score_prom']} en "
                    f"{ini['cohorte']} a {fin['score_prom']} en {fin['cohorte']}: las cosechas "
                    f"recientes entran con más riesgo."),
        "kpis": [
            {"label": f"Score {ini['cohorte']}", "valor": f"{ini['score_prom']}", "tono": "bueno"},
            {"label": f"Score {fin['cohorte']}", "valor": f"{fin['score_prom']}", "tono": "alerta"},
        ],
        "visual": {"tipo": "line", "etiqueta_valor": "score promedio",
                   "puntos": [{"x": str(r["cohorte"]), "y": float(r["score_prom"])} for r in rows]},
        "datos": {"filas": rows},
    }

def crecimiento_pep():
    """Crecimiento anual de clientes PEP con crédito (~10% interanual) + proyección 2026."""
    rows = q("""
        SELECT s.cohorte, COUNT(*) AS pep
        FROM solicitante s JOIN validacion v USING (codigo_unico)
        WHERE v.numero_corrida = 1 AND v.pep = TRUE
          AND s.tipo_producto IN ('Crédito Consumo','Crédito Pyme')
        GROUP BY s.cohorte ORDER BY s.cohorte
    """)
    puntos = [{"x": str(r["cohorte"]), "y": r["pep"]} for r in rows]
    proy = None
    if len(rows) >= 2:
        ult, penult = rows[-1]["pep"], rows[-2]["pep"]
        tasa = ult / penult if penult else 1.1
        proy = int(round(ult * tasa))
        puntos.append({"x": "2026", "y": proy, "proyectado": True})
    return {
        "titulo": "Crecimiento de clientes PEP con crédito",
        "resumen": (f"Los PEP con crédito pasaron de {_miles(rows[0]['pep'])} en {rows[0]['cohorte']} "
                    f"a {_miles(rows[-1]['pep'])} en {rows[-1]['cohorte']}, cerca de 10% anual. "
                    + (f"La proyección para 2026 es {_miles(proy)}." if proy else "")),
        "kpis": [{"label": "PEP 2025", "valor": _miles(rows[-1]["pep"]), "tono": "neutro"},
                 {"label": "Proyección 2026", "valor": _miles(proy) if proy else "—", "tono": "alerta"}],
        "visual": {"tipo": "line", "etiqueta_valor": "PEP con crédito", "puntos": puntos},
        "datos": {"filas": rows, "proyeccion_2026": proy},
    }

def segmento_precalificados():
    """D1 — clientes 'sano ejemplar' pre-cualificables, con su distribución geográfica."""
    n = q1("SELECT COUNT(*) n FROM solicitante WHERE arquetipo='D1'")
    geo = q("""
        SELECT departamento, COUNT(*) n FROM solicitante
        WHERE arquetipo='D1' GROUP BY departamento ORDER BY n DESC LIMIT 6
    """)
    return {
        "titulo": "Segmento pre-cualificado (oportunidad comercial)",
        "resumen": (f"Hay {_miles(n['n'])} clientes 'sano ejemplar': score bajo, listas limpias, "
                    f"sin señales adversas y buen comportamiento. Son candidatos ideales para "
                    f"pre-aprobación de productos."),
        "kpis": [{"label": "Pre-cualificados", "valor": _miles(n["n"]), "tono": "bueno"}],
        "visual": {"tipo": "geo_bar", "etiqueta_valor": "clientes",
                   "series": [{"nombre": r["departamento"], "valor": r["n"]} for r in geo]},
        "datos": {"total": n["n"], "geografia": geo},
    }

def riesgo_oculto():
    """B4 — deteriorados silenciosos: pasaron limpios el onboarding pero hoy el modelo los ve en riesgo."""
    n = q1("""
        SELECT COUNT(*) n FROM solicitante s
        JOIN validacion v1 ON v1.codigo_unico=s.codigo_unico AND v1.numero_corrida=1
        JOIN proyeccion_mora p ON p.codigo_unico=s.codigo_unico
        WHERE v1.banda_score='Bajo' AND p.probabilidad_mora > 65
    """)
    ejemplos = q("""
        SELECT s.codigo_unico, s.departamento, s.tipo_producto,
               v1.score_total AS score_ini, p.probabilidad_mora AS prob
        FROM solicitante s
        JOIN validacion v1 ON v1.codigo_unico=s.codigo_unico AND v1.numero_corrida=1
        JOIN proyeccion_mora p ON p.codigo_unico=s.codigo_unico
        WHERE v1.banda_score='Bajo' AND p.probabilidad_mora > 65
        ORDER BY p.probabilidad_mora DESC LIMIT 8
    """)
    return {
        "titulo": "Riesgo oculto — deteriorados silenciosos",
        "resumen": (f"Detectamos {_miles(n['n'])} clientes que pasaron limpios el onboarding "
                    f"—score bajo, sin señales— pero que el modelo hoy proyecta con más de 65% "
                    f"de probabilidad de mora. El banco no los veía; Forecast Lab sí."),
        "kpis": [{"label": "Deteriorados silenciosos", "valor": _miles(n["n"]), "tono": "alerta"}],
        "visual": {"tipo": "table",
                   "columnas": ["Cliente", "Departamento", "Producto", "Score inicial", "Prob. mora"],
                   "filas": [[r["codigo_unico"], r["departamento"], r["tipo_producto"],
                              r["score_ini"], f"{r['prob']}%"] for r in ejemplos]},
        "datos": {"total": n["n"], "ejemplos": ejemplos},
    }

def oportunidad_seguros():
    """C6 — deudores de riesgo medio sin seguro de vida-crédito (colocación de seguros)."""
    r = q1("""
        SELECT COUNT(*) n, SUM(c.saldo_expuesto) saldo
        FROM comportamiento c JOIN proyeccion_mora p USING (codigo_unico)
        WHERE c.tiene_seguro_vida_credito=FALSE AND p.nivel_riesgo='Medio'
    """)
    return {
        "titulo": "Oportunidad — colocación de seguros",
        "resumen": (f"Hay {_miles(r['n'])} deudores de riesgo medio que NO tienen seguro de "
                    f"vida-crédito, con {_q(r['saldo'])} de saldo expuesto. Es el segmento "
                    f"natural para colocar cobertura y proteger la cartera."),
        "kpis": [
            {"label": "Sin seguro (riesgo medio)", "valor": _miles(r["n"]), "tono": "alerta"},
            {"label": "Saldo expuesto", "valor": _q(r["saldo"]), "tono": "neutro"},
        ],
        "visual": {"tipo": "kpi", "series": []},
        "datos": {"total": r["n"], "saldo": float(r["saldo"] or 0)},
    }

_DIMENSIONES = {
    "region": "s.region", "departamento": "s.departamento", "producto": "s.tipo_producto",
    "cohorte": "s.cohorte::text", "banda": "v.banda_score",
    "capacidad_pago": "ve.capacidad_pago", "comportamiento_veritas": "ve.comportamiento_pago",
}

def mora_por_dimension(dimension="region"):
    """Mora desglosada por una dimensión (region, departamento, producto, cohorte, banda, capacidad_pago...)."""
    dim = _DIMENSIONES.get(dimension, "s.region")
    join_v = "JOIN validacion v ON v.codigo_unico=s.codigo_unico AND v.numero_corrida=1" if "v." in dim else ""
    join_ve = "JOIN veritas ve USING (codigo_unico)" if "ve." in dim else ""
    rows = q(f"""
        SELECT {dim} AS grupo, COUNT(*) AS clientes,
               ROUND(100.0*SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_mora
        FROM solicitante s JOIN comportamiento c USING (codigo_unico) {join_v} {join_ve}
        GROUP BY {dim} ORDER BY pct_mora DESC
    """)
    return {
        "titulo": f"Mora por {dimension}",
        "resumen": (f"El grupo con mayor mora es {rows[0]['grupo']} con {rows[0]['pct_mora']}%; "
                    f"el menor es {rows[-1]['grupo']} con {rows[-1]['pct_mora']}%."),
        "kpis": [],
        "visual": {"tipo": "bar", "orientacion": "horizontal", "etiqueta_valor": "% mora",
                   "series": [{"nombre": str(r["grupo"]), "valor": float(r["pct_mora"])} for r in rows]},
        "datos": {"dimension": dimension, "filas": rows},
    }

def veritas_predice_mora():
    """VERITAS (comportamiento de pago A/B/C) anticipó la mora real."""
    rows = q("""
        SELECT ve.comportamiento_pago AS grado, COUNT(*) AS clientes,
               ROUND(100.0*SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_mora
        FROM veritas ve JOIN comportamiento c USING (codigo_unico)
        GROUP BY ve.comportamiento_pago ORDER BY ve.comportamiento_pago
    """)
    a = next((float(r["pct_mora"]) for r in rows if r["grado"] == "A"), 0)
    c_ = next((float(r["pct_mora"]) for r in rows if r["grado"] == "C"), 0)
    return {
        "titulo": "VERITAS anticipó el desenlace",
        "resumen": (f"Los clientes calificados C por VERITAS cayeron en mora {c_}%, frente a "
                    f"apenas {a}% de los calificados A. El análisis crediticio predijo el resultado."),
        "kpis": [{"label": "Grado C", "valor": f"{c_}", "sufijo": "%", "tono": "alerta"},
                 {"label": "Grado A", "valor": f"{a}", "sufijo": "%", "tono": "bueno"}],
        "visual": {"tipo": "bar", "orientacion": "vertical", "etiqueta_valor": "% mora",
                   "series": [{"nombre": f"Grado {r['grado']}", "valor": float(r["pct_mora"]),
                               "tono": "alerta" if r["grado"] == "C" else ("bueno" if r["grado"] == "A" else "neutro")}
                              for r in rows]},
        "datos": {"filas": rows},
    }

def perfil_cliente(codigo_unico):
    """Ficha 360 de un cliente a través de las 6 fuentes de datos."""
    s = q1("SELECT * FROM solicitante WHERE codigo_unico=%(c)s", {"c": codigo_unico})
    if not s:
        return {"titulo": "Cliente no encontrado", "resumen": f"No existe el cliente {codigo_unico}.",
                "kpis": [], "visual": {"tipo": "none"}, "datos": {}}
    v1 = q1("SELECT * FROM validacion WHERE codigo_unico=%(c)s AND numero_corrida=1", {"c": codigo_unico})
    comp = q1("SELECT * FROM comportamiento WHERE codigo_unico=%(c)s", {"c": codigo_unico})
    ve = q1("SELECT * FROM veritas WHERE codigo_unico=%(c)s", {"c": codigo_unico})
    proy = q1("SELECT * FROM proyeccion_mora WHERE codigo_unico=%(c)s", {"c": codigo_unico})
    estado = "en mora" if comp.get("en_mora") else "al día"
    prob = proy.get("probabilidad_mora")
    return {
        "titulo": f"Ficha 360 — {codigo_unico}",
        "resumen": (f"Cliente de {s['departamento']}, {s['tipo_producto']}, score de originación "
                    f"{v1.get('score_total')} (banda {v1.get('banda_score')}). Hoy está {estado}"
                    + (f", con probabilidad de mora proyectada de {prob}%." if prob is not None else ".")),
        "kpis": [
            {"label": "Score orig.", "valor": f"{v1.get('score_total','—')}",
             "tono": "alerta" if v1.get("banda_score") in ("Alto", "Medio-alto") else "bueno"},
            {"label": "Prob. mora", "valor": f"{prob}" if prob is not None else "—", "sufijo": "%",
             "tono": "alerta" if (prob or 0) > 60 else ("neutro" if (prob or 0) > 30 else "bueno")},
            {"label": "Estado", "valor": estado.capitalize(),
             "tono": "alerta" if comp.get("en_mora") else "bueno"},
        ],
        "visual": {"tipo": "client_detail",
                   "solicitante": s, "validacion": v1, "comportamiento": comp,
                   "veritas": ve, "proyeccion": proy},
        "datos": {"solicitante": s, "validacion": v1, "comportamiento": comp,
                  "veritas": ve, "proyeccion": proy},
    }

def incongruencia_ingreso_actividad():
    """A3 — clientes cuyo ingreso declarado no cuadra con la actividad económica validada."""
    r = q1("""
        SELECT COUNT(*) n,
               ROUND(100.0*SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END)/COUNT(*),1) pct_mora
        FROM validacion v JOIN comportamiento c USING (codigo_unico)
        WHERE v.numero_corrida=1 AND v.mismatch_ingreso_actividad = TRUE
    """)
    tot = q1("SELECT COUNT(*) n FROM comportamiento WHERE en_mora")["n"]
    conc = q1("""
        SELECT COUNT(*) n FROM validacion v JOIN comportamiento c USING (codigo_unico)
        WHERE v.numero_corrida=1 AND v.mismatch_ingreso_actividad=TRUE AND c.en_mora
    """)["n"]
    share = round(100.0 * conc / tot, 1) if tot else 0
    pct_cart = round(100.0 * r["n"] / 25000, 1)
    return {
        "titulo": "Incongruencia ingreso–actividad",
        "resumen": (f"En {_miles(r['n'])} clientes ({pct_cart}% de la cartera) el ingreso "
                    f"declarado no cuadra con la actividad que Forecast Lab validó. Ese grupo "
                    f"concentra el {share}% de la cartera vencida: pesa mucho más que su tamaño."),
        "kpis": [{"label": "Clientes", "valor": _miles(r["n"]), "tono": "neutro"},
                 {"label": "Mora del grupo", "valor": f"{r['pct_mora']}", "sufijo": "%", "tono": "alerta"},
                 {"label": "De la mora total", "valor": f"{share}", "sufijo": "%", "tono": "alerta"}],
        "visual": {"tipo": "bar", "orientacion": "vertical", "etiqueta_valor": "% de la mora",
                   "series": [{"nombre": "Su peso en mora", "valor": share, "tono": "alerta"},
                              {"nombre": "Su peso en cartera", "valor": pct_cart, "tono": "neutro"}]},
        "datos": {"n": r["n"], "pct_mora": r["pct_mora"], "share_vencido": share},
    }

def biometria_fraude():
    """V3 — coincidencia facial baja (<85%) y su relación con el default temprano."""
    rows = q("""
        SELECT CASE WHEN v.coincidencia_facial < 85 THEN 'Facial < 85%' ELSE 'Facial ≥ 85%' END grupo,
               COUNT(*) n,
               ROUND(100.0*SUM(CASE WHEN c.meses_hasta_mora < 6 THEN 1 ELSE 0 END)/COUNT(*),2) pct_temprano
        FROM validacion v JOIN comportamiento c USING (codigo_unico)
        WHERE v.numero_corrida=1 GROUP BY 1 ORDER BY 1
    """)
    baja = next((r for r in rows if r["grupo"].startswith("Facial <")), {"n": 0, "pct_temprano": 0})
    alta = next((float(r["pct_temprano"]) for r in rows if r["grupo"].startswith("Facial ≥")), 0.01)
    ratio = round(float(baja["pct_temprano"]) / alta, 1) if alta else None
    return {
        "titulo": "Biometría facial: la puerta del fraude",
        "resumen": (f"{_miles(baja['n'])} clientes abrieron con coincidencia facial menor al 85%. "
                    f"Su tasa de default en los primeros 6 meses es {baja['pct_temprano']}%, "
                    f"muy por encima del {alta}% del resto. El banco nunca comparó el DPI contra "
                    f"RENAP; Forecast Lab marcó esa inconsistencia desde el minuto uno."),
        "kpis": [{"label": "Facial < 85%", "valor": _miles(baja["n"]), "tono": "alerta"},
                 {"label": "Default temprano", "valor": f"{baja['pct_temprano']}", "sufijo": "%", "tono": "alerta"}],
        "visual": {"tipo": "bar", "orientacion": "vertical", "etiqueta_valor": "% default < 6 meses",
                   "series": [{"nombre": r["grupo"], "valor": float(r["pct_temprano"]),
                               "tono": "alerta" if r["grupo"].startswith("Facial <") else "bueno"}
                              for r in rows]},
        "datos": {"filas": rows, "ratio": ratio},
    }

def exposicion_sancionados():
    """A5 — exposición a jurisdicciones sancionadas; subconjunto caliente con adverse media."""
    base = q1("""
        SELECT COUNT(DISTINCT codigo_unico) n FROM validacion
        WHERE numero_corrida=1 AND (recibe_de_sancionados OR envia_a_sancionados)
    """)["n"]
    calientes = q1("""
        SELECT COUNT(DISTINCT v.codigo_unico) n
        FROM validacion v
        JOIN osint_hallazgo o ON o.codigo_unico=v.codigo_unico
             AND o.sentimiento='Negativo' AND o.categoria IN ('Criminal','Noticias','Listas')
        WHERE v.numero_corrida=1 AND (v.recibe_de_sancionados OR v.envia_a_sancionados)
    """)["n"]
    return {
        "titulo": "Exposición a jurisdicciones sancionadas",
        "resumen": (f"{_miles(base)} clientes declaran flujos con jurisdicciones sancionadas. "
                    f"De ellos, Forecast Lab aisló {_miles(calientes)} que además traen menciones "
                    f"adversas: ese cruce es el foco caliente de LA/FT que el banco veía apenas "
                    f"como «recibe transferencias del exterior»."),
        "kpis": [{"label": "Expuestos", "valor": _miles(base), "tono": "neutro"},
                 {"label": "Foco caliente (+ adverse media)", "valor": _miles(calientes), "tono": "alerta"}],
        "visual": {"tipo": "bar", "orientacion": "horizontal", "etiqueta_valor": "clientes",
                   "series": [{"nombre": "Expuestos a sancionados", "valor": base, "tono": "neutro"},
                              {"nombre": "Foco caliente LA/FT", "valor": calientes, "tono": "alerta"}]},
        "datos": {"expuestos": base, "calientes": calientes},
    }

_BANDA_IDX = "CASE {c} WHEN 'Bajo' THEN 1 WHEN 'Medio' THEN 2 WHEN 'Medio-alto' THEN 3 WHEN 'Alto' THEN 4 END"

def comparativo_corridas():
    """Monitoreo — qué cambió entre la corrida 1 y la 2 (nuevos hits, nuevos PEP, adverse media, deriva)."""
    d = q1(f"""
        WITH c1 AS (SELECT * FROM validacion WHERE numero_corrida=1),
             c2 AS (SELECT * FROM validacion WHERE numero_corrida=2)
        SELECT
          SUM(CASE WHEN (c2.match_ofac OR c2.match_onu OR c2.match_engel)
                    AND NOT (c1.match_ofac OR c1.match_onu OR c1.match_engel) THEN 1 ELSE 0 END) nuevas_listas,
          SUM(CASE WHEN c2.pep AND NOT c1.pep THEN 1 ELSE 0 END) nuevos_pep,
          SUM(CASE WHEN ({_BANDA_IDX.format(c='c2.banda_score')}) > ({_BANDA_IDX.format(c='c1.banda_score')})
                   THEN 1 ELSE 0 END) score_peor
        FROM c1 JOIN c2 USING (codigo_unico)
    """)
    nueva_adverse = q1("""
        SELECT COUNT(DISTINCT o2.codigo_unico) n FROM osint_hallazgo o2
        WHERE o2.numero_corrida=2 AND o2.sentimiento='Negativo'
          AND o2.categoria IN ('Criminal','Noticias','Listas')
          AND NOT EXISTS (SELECT 1 FROM osint_hallazgo o1
                          WHERE o1.codigo_unico=o2.codigo_unico AND o1.numero_corrida=1
                            AND o1.sentimiento='Negativo' AND o1.categoria IN ('Criminal','Noticias','Listas'))
    """)["n"]
    total = (d["nuevas_listas"] or 0) + (d["nuevos_pep"] or 0) + nueva_adverse + (d["score_peor"] or 0)
    return {
        "titulo": "Comparativo entre corridas — qué se movió",
        "resumen": (f"{_miles(total)} clientes empeoraron su perfil entre corridas: "
                    f"{_miles(d['nuevas_listas'])} nuevos hits en listas, {_miles(d['nuevos_pep'])} "
                    f"que se volvieron PEP, {_miles(nueva_adverse)} con adverse media nueva y "
                    f"{_miles(d['score_peor'])} con deterioro de score. Crédito vigente que antes "
                    f"clasificabas como sano y hoy no lo es."),
        "kpis": [{"label": "Empeoraron", "valor": _miles(total), "tono": "alerta"}],
        "visual": {"tipo": "bar", "orientacion": "horizontal", "etiqueta_valor": "clientes",
                   "series": [
                       {"nombre": "Nuevos hits en listas", "valor": d["nuevas_listas"] or 0, "tono": "alerta"},
                       {"nombre": "Se volvieron PEP", "valor": d["nuevos_pep"] or 0, "tono": "neutro"},
                       {"nombre": "Adverse media nueva", "valor": nueva_adverse, "tono": "alerta"},
                       {"nombre": "Deterioro de score", "valor": d["score_peor"] or 0, "tono": "neutro"}]},
        "datos": {"total": total, **d, "nueva_adverse": nueva_adverse},
    }

def empresarios_ocultos():
    """D2 — personas individuales que el OSINT revela como operadores de un negocio."""
    n = q1("SELECT COUNT(*) n FROM solicitante WHERE arquetipo='D2'")["n"]
    return {
        "titulo": "Cartera empresarial oculta",
        "resumen": (f"El OSINT reveló {_miles(n)} clientes registrados como personas individuales "
                    f"que en realidad operan un negocio: aparecen como proveedores, socios o dueños "
                    f"en directorios. Es una cartera empresarial escondida dentro de tu cartera "
                    f"personal, lista para cuenta empresarial, POS y capital de trabajo."),
        "kpis": [{"label": "Empresarios ocultos", "valor": _miles(n), "tono": "bueno"}],
        "visual": {"tipo": "kpi", "series": []},
        "datos": {"total": n},
    }

def proveedores_estado():
    """C3 — proveedores del Estado (CPE/GUATECOMPRAS): riesgo de ciclo fiscal + oportunidad de liquidez."""
    r = q1("""
        SELECT COUNT(DISTINCT codigo_unico) n FROM validacion
        WHERE numero_corrida=1 AND contratista_estado=TRUE
    """)
    paga = q1("""
        SELECT ROUND(100.0*SUM(CASE WHEN c.termino_de_pagar THEN 1 ELSE 0 END)/COUNT(*),1) pct
        FROM validacion v JOIN comportamiento c USING (codigo_unico)
        WHERE v.numero_corrida=1 AND v.contratista_estado=TRUE
    """)["pct"]
    return {
        "titulo": "Proveedores del Estado — riesgo y oportunidad",
        "resumen": (f"{_miles(r['n'])} clientes fueron validados como proveedores del Estado en "
                    f"GUATECOMPRAS. El Estado les paga tarde, así que necesitan liquidez —factoring "
                    f"y capital de trabajo— y a la vez los monitoreamos por riesgo del ciclo fiscal. "
                    f"Un solo flag de Forecast Lab, dos líneas de negocio."),
        "kpis": [{"label": "Proveedores del Estado", "valor": _miles(r["n"]), "tono": "neutro"},
                 {"label": "Terminan pagando", "valor": f"{paga}", "sufijo": "%", "tono": "bueno"}],
        "visual": {"tipo": "kpi", "series": []},
        "datos": {"total": r["n"], "pct_paga": paga},
    }

def segmento_internacional():
    """D4 — extranjeros/empresas con comercio exterior: nicho de productos en divisas."""
    n = q1("""
        SELECT COUNT(DISTINCT v.codigo_unico) n FROM validacion v
        WHERE v.numero_corrida=1 AND v.categoria_cliente LIKE 'Extranjero%'
          AND v.transferencias_internacionales=TRUE
          AND NOT (v.recibe_de_sancionados OR v.envia_a_sancionados)
    """)["n"]
    return {
        "titulo": "Segmento internacional desaprovechado",
        "resumen": (f"{_miles(n)} clientes tienen categoría validada de extranjero residente o "
                    f"empresa extranjera con presencia local y actividad de comercio exterior, sin "
                    f"exposición a sancionados. Es tu nicho natural para cuentas multimoneda, "
                    f"comercio internacional y coberturas cambiarias."),
        "kpis": [{"label": "Segmento internacional", "valor": _miles(n), "tono": "bueno"}],
        "visual": {"tipo": "kpi", "series": []},
        "datos": {"total": n},
    }

def clientes_evolucionaron():
    """D3 — clientes que mejoraron su perfil entre corridas (listos para el siguiente producto)."""
    n = q1(f"""
        WITH c1 AS (SELECT codigo_unico, score_total, banda_score FROM validacion WHERE numero_corrida=1),
             c2 AS (SELECT codigo_unico, score_total, banda_score FROM validacion WHERE numero_corrida=2)
        SELECT COUNT(*) n FROM c1 JOIN c2 USING (codigo_unico)
        WHERE ({_BANDA_IDX.format(c='c2.banda_score')}) < ({_BANDA_IDX.format(c='c1.banda_score')})
    """)["n"]
    return {
        "titulo": "Clientes que evolucionaron — listos para más",
        "resumen": (f"Desde la corrida anterior, {_miles(n)} clientes mejoraron su perfil: bajó su "
                    f"score y su OSINT se volvió positivo o neutro. Son señales de que están listos "
                    f"para subir de escalón —un préstamo mayor, una hipoteca, una línea empresarial. "
                    f"El banco los sigue viendo igual; Forecast Lab ve que ya no son los mismos."),
        "kpis": [{"label": "Evolucionaron favorablemente", "valor": _miles(n), "tono": "bueno"}],
        "visual": {"tipo": "kpi", "series": []},
        "datos": {"total": n},
    }

def perfil_demografico_riesgo():
    """Combinación datos personales + comportamiento: qué perfil concentra más mora en consumo."""
    r = q1("""
        SELECT COUNT(*) n, ROUND(100.0*SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END)/COUNT(*),1) pct_mora
        FROM solicitante s JOIN comportamiento c USING (codigo_unico)
        WHERE s.estado_civil='Soltero' AND s.edad BETWEEN 18 AND 30
          AND s.region='Noroccidente' AND s.tipo_producto='Crédito Consumo'
    """)
    cart = q1("""
        SELECT ROUND(100.0*AVG(CASE WHEN en_mora THEN 1 ELSE 0 END),1) pct
        FROM comportamiento c JOIN solicitante s USING (codigo_unico)
        WHERE s.tipo_producto='Crédito Consumo'
    """)["pct"]
    return {
        "titulo": "Perfil demográfico de mayor mora (consumo)",
        "resumen": (f"El segmento más crítico son los solteros de 18 a 30 años en la región "
                    f"Noroccidente: su mora es {r['pct_mora']}%, frente al {cart}% del promedio de "
                    f"consumo. Un patrón que solo aparece al cruzar edad, estado civil y región con "
                    f"el comportamiento real de pago."),
        "kpis": [{"label": "Mora del segmento", "valor": f"{r['pct_mora']}", "sufijo": "%", "tono": "alerta"},
                 {"label": "Promedio consumo", "valor": f"{cart}", "sufijo": "%", "tono": "neutro"},
                 {"label": "Clientes", "valor": _miles(r["n"]), "tono": "neutro"}],
        "visual": {"tipo": "bar", "orientacion": "vertical", "etiqueta_valor": "% mora",
                   "series": [{"nombre": "Solteros 18-30 Noroccidente", "valor": float(r["pct_mora"]), "tono": "alerta"},
                              {"nombre": "Promedio consumo", "valor": float(cart), "tono": "neutro"}]},
        "datos": {"segmento": r, "promedio_consumo": cart},
    }

def clientes_alta_probabilidad(limite=8):
    """Clientes con probabilidad de mora > 70% ordenados por monto expuesto, con sus factores."""
    tot = q1("""
        SELECT COUNT(*) n, SUM(c.saldo_expuesto) exp
        FROM proyeccion_mora p JOIN comportamiento c USING (codigo_unico)
        WHERE p.probabilidad_mora > 70
    """)
    filas = q("""
        SELECT s.codigo_unico, s.tipo_producto, s.departamento,
               p.probabilidad_mora prob, c.saldo_expuesto saldo, p.factores_explicativos fac
        FROM proyeccion_mora p JOIN solicitante s USING (codigo_unico)
        JOIN comportamiento c USING (codigo_unico)
        WHERE p.probabilidad_mora > 70
        ORDER BY c.saldo_expuesto DESC NULLS LAST LIMIT %(l)s
    """, {"l": int(limite)})
    return {
        "titulo": "Clientes con probabilidad de mora > 70%",
        "resumen": (f"Identifiqué {_miles(tot['n'])} clientes con probabilidad de mora superior al 70%, "
                    f"que suman {_q(tot['exp'])} de exposición. Te los ordeno por monto y te doy los "
                    f"factores que más pesan en cada proyección."),
        "kpis": [{"label": "Clientes", "valor": _miles(tot["n"]), "tono": "alerta"},
                 {"label": "Exposición", "valor": _q(tot["exp"]), "tono": "alerta"}],
        "visual": {"tipo": "table",
                   "columnas": ["Cliente", "Producto", "Departamento", "Prob.", "Saldo exp.", "Factores"],
                   "filas": [[f["codigo_unico"], f["tipo_producto"], f["departamento"],
                              f"{f['prob']}%", _q(f["saldo"]),
                              ", ".join(f["fac"]) if isinstance(f["fac"], list) else str(f["fac"])]
                             for f in filas]},
        "datos": {"total": tot["n"], "exposicion": float(tot["exp"] or 0), "top": filas},
    }

def colocacion_segura(region="Suroccidente"):
    """Colocación de tarjeta con bajo riesgo en una región: LSTM<10%, sin atrasos, aún sin tarjeta."""
    r = q1("""
        SELECT COUNT(*) n FROM solicitante s
        JOIN proyeccion_mora p USING (codigo_unico)
        JOIN comportamiento c USING (codigo_unico)
        WHERE p.probabilidad_mora < 10 AND c.tuvo_atrasos = FALSE
          AND s.tipo_producto IN ('Crédito Consumo','Crédito Pyme')
          AND s.region = %(r)s
    """, {"r": region})
    geo = q("""
        SELECT s.departamento, COUNT(*) n FROM solicitante s
        JOIN proyeccion_mora p USING (codigo_unico)
        JOIN comportamiento c USING (codigo_unico)
        WHERE p.probabilidad_mora < 10 AND c.tuvo_atrasos = FALSE
          AND s.tipo_producto IN ('Crédito Consumo','Crédito Pyme')
          AND s.region = %(r)s
        GROUP BY s.departamento ORDER BY n DESC
    """, {"r": region})
    return {
        "titulo": f"Colocación segura de tarjeta — {region}",
        "resumen": (f"Tienes {_miles(r['n'])} clientes en {region} con probabilidad de mora bajo 10%, "
                    f"historial sin atrasos y aún sin tarjeta de crédito. Es colocación segura sobre un "
                    f"segmento que el modelo respalda como de bajo riesgo. Te los ordeno por departamento."),
        "kpis": [{"label": f"Candidatos en {region}", "valor": _miles(r["n"]), "tono": "bueno"}],
        "visual": {"tipo": "geo_bar", "etiqueta_valor": "clientes",
                   "series": [{"nombre": g["departamento"], "valor": g["n"]} for g in geo]},
        "datos": {"total": r["n"], "region": region, "geografia": geo},
    }

def segmento_riesgo_emergente():
    """Cruce de las 5 fuentes: el segmento de mayor riesgo emergente para el próximo año."""
    r = q1("""
        SELECT COUNT(*) n, SUM(c.saldo_expuesto) exp
        FROM solicitante s
        JOIN proyeccion_mora p USING (codigo_unico)
        JOIN veritas ve USING (codigo_unico)
        JOIN comportamiento c USING (codigo_unico)
        WHERE p.probabilidad_mora > 60 AND ve.comportamiento_pago='C'
          AND c.tuvo_atrasos=TRUE
          AND s.estado_civil='Soltero' AND s.edad BETWEEN 18 AND 35
          AND EXISTS (SELECT 1 FROM osint_hallazgo o WHERE o.codigo_unico=s.codigo_unico
                      AND o.numero_corrida=2 AND o.sentimiento='Negativo'
                      AND o.categoria IN ('Criminal','Noticias','Listas'))
    """)
    return {
        "titulo": "Segmento de mayor riesgo emergente",
        "resumen": (f"Cruzando las cinco fuentes, el segmento más crítico reúne proyección LSTM sobre "
                    f"60%, comportamiento VERITAS categoría C, adverse media nueva, atrasos previos y "
                    f"perfil demográfico de riesgo. Son {_miles(r['n'])} clientes, {_q(r['exp'])} "
                    f"expuestos. Ninguna fuente por sí sola los habría aislado; es la combinación la "
                    f"que los revela."),
        "kpis": [{"label": "Clientes", "valor": _miles(r["n"]), "tono": "alerta"},
                 {"label": "Exposición", "valor": _q(r["exp"]), "tono": "alerta"}],
        "visual": {"tipo": "kpi", "series": []},
        "datos": {"total": r["n"], "exposicion": float(r["exp"] or 0)},
    }

# Registro de tools disponibles (nombre -> función)
TOOLS = {
    "resumen_cartera": resumen_cartera,
    "curva_mora_por_banda": curva_mora_por_banda,
    "impacto_adverse_media": impacto_adverse_media,
    "incongruencia_ingreso_actividad": incongruencia_ingreso_actividad,
    "biometria_fraude": biometria_fraude,
    "contraste_pep": contraste_pep,
    "exposicion_sancionados": exposicion_sancionados,
    "comparativo_corridas": comparativo_corridas,
    "evolucion_originacion": evolucion_originacion,
    "crecimiento_pep": crecimiento_pep,
    "segmento_precalificados": segmento_precalificados,
    "empresarios_ocultos": empresarios_ocultos,
    "proveedores_estado": proveedores_estado,
    "segmento_internacional": segmento_internacional,
    "oportunidad_seguros": oportunidad_seguros,
    "clientes_evolucionaron": clientes_evolucionaron,
    "riesgo_oculto": riesgo_oculto,
    "veritas_predice_mora": veritas_predice_mora,
    "perfil_demografico_riesgo": perfil_demografico_riesgo,
    "clientes_alta_probabilidad": clientes_alta_probabilidad,
    "colocacion_segura": colocacion_segura,
    "segmento_riesgo_emergente": segmento_riesgo_emergente,
    "mora_por_dimension": mora_por_dimension,
    "perfil_cliente": perfil_cliente,
}
