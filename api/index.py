# -*- coding: utf-8 -*-
"""
Función serverless de Vercel para el demo "Forecast Lab · Banrural".

Expone:
  GET  /api/config   -> modelo/voz (no sensible)
  GET  /api/session  -> token efímero de la Realtime API de OpenAI
  POST /api/tool     -> ejecuta una tool contra la base (DATABASE_URL) y devuelve el contrato visual

Los estáticos se sirven desde /public (CDN de Vercel). Las variables de entorno
(OPENAI_API_KEY, DATABASE_URL, REALTIME_MODEL, REALTIME_VOICE) se configuran en Vercel.
"""

import os
import sys
import json
import decimal
import datetime as _dt

# Permite importar _tools/_instructions tanto en Vercel (cwd = api/) como en local
sys.path.insert(0, os.path.dirname(__file__))

# En local carga el .env de la raíz; en Vercel no existe y usa las env vars del panel.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass

# En Linux (Vercel) el bundle de certifi ya valida a api.openai.com; truststore es
# opcional (solo hace falta en máquinas con inspección TLS, como Windows local).
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse, RedirectResponse

import _tools as T
from _instructions import SYSTEM_INSTRUCTIONS, TOOL_SCHEMAS

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
REALTIME_MODEL = os.environ.get("REALTIME_MODEL", "gpt-realtime")
REALTIME_VOICE = os.environ.get("REALTIME_VOICE", "marin")

app = FastAPI(title="Forecast Lab · Banrural — Demo")


def _json_default(o):
    if isinstance(o, decimal.Decimal):
        return float(o)
    if isinstance(o, (_dt.date, _dt.datetime)):
        return o.isoformat()
    return str(o)


def _json(payload, status_code=200):
    return Response(content=json.dumps(payload, default=_json_default, ensure_ascii=False),
                    media_type="application/json", status_code=status_code)


@app.get("/api/config")
def config():
    return {"model": REALTIME_MODEL, "voice": REALTIME_VOICE, "key_presente": bool(OPENAI_API_KEY)}


@app.get("/api/session")
async def session():
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "OPENAI_API_KEY no configurada"}, status_code=500)
    body = {
        "session": {
            "type": "realtime",
            "model": REALTIME_MODEL,
            "instructions": SYSTEM_INSTRUCTIONS,
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad", "threshold": 0.68,
                        "prefix_padding_ms": 300, "silence_duration_ms": 900,
                        "create_response": True, "interrupt_response": True,
                    },
                },
                "output": {"voice": REALTIME_VOICE},
            },
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
        }
    }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post("https://api.openai.com/v1/realtime/client_secrets",
                                  headers=headers, json=body)
        if r.status_code >= 400:
            return JSONResponse({"error": "OpenAI rechazó la sesión",
                                 "status": r.status_code, "detalle": r.text}, status_code=502)
        data = r.json()
        data["model"] = REALTIME_MODEL
        return _json(data)
    except Exception as e:
        return JSONResponse({"error": f"No se pudo contactar OpenAI: {e}"}, status_code=502)


@app.post("/api/tool")
async def tool(request: Request):
    payload = await request.json()
    name = payload.get("name")
    args = payload.get("arguments", {}) or {}
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except Exception:
            args = {}
    fn = T.TOOLS.get(name)
    if not fn:
        return _json({"error": f"Tool desconocida: {name}"}, status_code=404)
    try:
        return _json(fn(**args))
    except Exception as e:
        return _json({"error": f"Error ejecutando {name}: {e}"}, status_code=500)


# ---------------------------------------------------------------------------
# Front-end estático servido por la MISMA función (montado al final para que las
# rutas /api/* tengan prioridad). En Vercel, public/ se incluye vía includeFiles.
# Sirve también en local a través de dev.py.
# ---------------------------------------------------------------------------
from fastapi.staticfiles import StaticFiles  # noqa: E402

# Estáticos: primero api/static (siempre incluido en la función de Vercel), luego
# ../public como respaldo (útil en local). Se usa el primero que exista.
_HERE = os.path.dirname(__file__)
for _cand in (os.path.join(_HERE, "static"), os.path.join(_HERE, "..", "public")):
    if os.path.isdir(_cand):
        app.mount("/", StaticFiles(directory=_cand, html=True), name="static")
        break
