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

## Parte B · Deploy en Vercel desde GitHub (~5 min)

El repo ya está en **https://github.com/cmasaya1971/forcastia**. Vercel se conecta a él y
redeploya solo en cada `git push`.

1. Entrá a **https://vercel.com** → *Add New… → Project*.
2. *Import Git Repository* → elegí **cmasaya1971/forcastia** (autorizá GitHub si lo pide).
3. En la pantalla de configuración, **antes de "Deploy"**, abrí *Environment Variables* y agregá:
   | Name | Value |
   |---|---|
   | `OPENAI_API_KEY` | tu key de OpenAI (`sk-proj-...`) |
   | `DATABASE_URL` | el connection string de Neon |
   | `REALTIME_MODEL` | `gpt-realtime` (opcional) |
   | `REALTIME_VOICE` | `marin` (opcional) |
4. **Deploy**. Vercel detecta `requirements.txt` (función Python en `api/`) y sirve `public/`.
5. Te da la **URL pública** `https://forcastia-xxxx.vercel.app`. Esa la compartís.

> Cada vez que hagamos `git push` a `main`, Vercel redeploya automáticamente.
> Si agregás/ cambiás env vars después, usá *Deployments → Redeploy* para que tomen efecto.

---

## Notas importantes

- **Warm-up:** el plan gratis de Neon suspende la base tras inactividad; hacé una pregunta 1 minuto antes de la demo para “despertarla”.
- **Exposición de la key:** al ser público sin login, cualquiera con la URL puede usar la voz y consumir tu crédito de OpenAI. Si querés, activá la **Password Protection** de Vercel (Settings → Deployment Protection) o te agrego una contraseña simple.
- **Secretos:** el `.env` y la contraseña de la base nunca se suben (`.vercelignore`). En la nube todo sale de las env vars de Vercel.
- **Iterar:** editás en `public/` o `api/` (fuente única), probás en local con `python dev.py`, y cuando estés conforme: `vercel --prod`. No hay copias que sincronizar.
