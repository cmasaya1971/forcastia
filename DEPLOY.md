# Publicar el demo en Vercel

La app tiene **una sola fuente de código** que sirve a los dos entornos (local y Vercel):

```
api/index.py        # la app FastAPI (API): /api/config, /api/session, /api/tool
api/_tools.py       # tools (consultan la base vía DATABASE_URL o PG* local)
api/_instructions.py
public/             # front-end estático (index.html, app.js, styles.css, logos)
dev.py              # LANZADOR LOCAL: reusa api/ + public/  ->  python dev.py
requirements.txt    # dependencias Python
vercel.json         # enruta /api/* a la función
.vercelignore       # evita subir .env, etc.
```

- **Local (tu máquina):** `python dev.py`  → http://localhost:8000
- **Producción (Vercel):** despliega `api/` (función) + `public/` (CDN).

Ambos usan EXACTAMENTE los mismos archivos, así que lo que editás en local sale igual en Vercel.

Necesitás dos cosas gratis: una base **Neon** (Postgres en la nube) y una cuenta **Vercel**.

---

## Parte A · Base de datos en Neon (~5 min)

1. Entrá a **https://neon.tech** y creá cuenta gratis (GitHub/Google).
2. **Create project** → nombre `demoscoring`, región cercana (p. ej. AWS US East).
3. Copiá el **Connection string** (Dashboard → *Connection Details*). Se ve así:
   ```
   postgresql://USUARIO:PASSWORD@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
4. **Cargar los datos** (desde la carpeta del proyecto, en tu máquina):
   ```bash
   export DATABASE_URL='postgresql://...tu string de Neon...'
   python generate.py
   ```
   Crea las 6 tablas y carga los 25,000 clientes en segundos (mismos patrones, `SEED=42`).
   > El generador aplica el esquema solo; no hace falta correr `schema.sql` aparte.

---

## Parte B · Deploy en Vercel (~5 min)

1. Instalá la CLI (requiere Node):
   ```bash
   npm i -g vercel
   vercel login
   ```
2. En la carpeta del proyecto, primer deploy (preview):
   ```bash
   vercel
   ```
   Aceptá los prompts (link/create project, root = esta carpeta).
3. Configurá las **variables de entorno** (Production):
   ```bash
   vercel env add OPENAI_API_KEY production
   vercel env add DATABASE_URL production
   vercel env add REALTIME_MODEL production      # valor: gpt-realtime   (opcional)
   vercel env add REALTIME_VOICE production       # valor: marin          (opcional)
   ```
   (o en el dashboard: Settings → Environment Variables)
4. Deploy a producción:
   ```bash
   vercel --prod
   ```
5. Vercel te da una **URL pública** `https://...vercel.app`. Esa es la que compartís.

---

## Notas importantes

- **Warm-up:** el plan gratis de Neon suspende la base tras inactividad; hacé una pregunta 1 minuto antes de la demo para “despertarla”.
- **Exposición de la key:** al ser público sin login, cualquiera con la URL puede usar la voz y consumir tu crédito de OpenAI. Si querés, activá la **Password Protection** de Vercel (Settings → Deployment Protection) o te agrego una contraseña simple.
- **Secretos:** el `.env` y la contraseña de la base nunca se suben (`.vercelignore`). En la nube todo sale de las env vars de Vercel.
- **Iterar:** editás en `public/` o `api/` (fuente única), probás en local con `python dev.py`, y cuando estés conforme: `vercel --prod`. No hay copias que sincronizar.
