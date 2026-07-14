# -*- coding: utf-8 -*-
"""
Servidor LOCAL de desarrollo. Usa exactamente el MISMO código que se despliega en
Vercel (api/index.py + api/_tools.py + api/_instructions.py) y sirve los estáticos
de public/. Así el entorno local y el de producción (Vercel) son idénticos.

Uso:
    python dev.py
Abrir: http://localhost:8000

Conexión a la base:
  - Local: usa las variables PG* (PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE) o el
    .env de la raíz. Si definís DATABASE_URL, usa esa (útil para probar contra Neon).
"""

import os
import sys

# Reusar la app de la función de Vercel
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))
from index import app  # noqa: E402  (api/index.py)

from fastapi.staticfiles import StaticFiles  # noqa: E402

# Servir el front-end (en Vercel esto lo hace el CDN desde /public)
_PUBLIC = os.path.join(os.path.dirname(__file__), "public")
app.mount("/", StaticFiles(directory=_PUBLIC, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
