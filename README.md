# Base de datos del demo "Verifiquemos · Banrural" — `demoscoring`

Genera y puebla la base **PostgreSQL** del demo con ~25,000 clientes, 5 años de
historia (2021–2025) y 2 corridas de monitoreo por cliente. Los datos están
**sembrados** con los 22 arquetipos y las 6 reglas transversales descritas en
`ESPECIFICACION_GENERACION_DATOS.md`, de modo que cada cliente es una **historia
internamente consistente** a través de las 6 fuentes.

## Requisitos

- **PostgreSQL 18** local (`localhost:5432`, base `demoscoring`, usuario `postgres`).
- **Python 3.13** con el driver `psycopg` (v3):
  ```bash
  python -m pip install "psycopg[binary]"
  ```
- Cliente `psql` (viene con PostgreSQL) para el esquema y la verificación.

## Entregables

| Archivo | Qué es |
|---|---|
| `schema.sql` | DDL completo: 6 tablas + 16 índices (idempotente, `DROP + CREATE`). |
| `generate.py` | Generador con semilla fija (`SEED=42`), arquetipos y reglas transversales. |
| `verify.sql` | Las 14 verificaciones obligatorias de la sección 7. |
| `REPORTE_VERIFICACION.txt` | Salida de la última corrida de `verify.sql` (todas pasan). |
| `README.md` | Este archivo. |

### La aplicación (asistente de voz)

La app vive en `api/` (backend FastAPI) + `public/` (front-end) — **una sola fuente** para
local y para Vercel:

- **Correr en local:** `python dev.py` → http://localhost:8000
  (necesita `PGPASSWORD` en el entorno o en `.env`, y `OPENAI_API_KEY` en `.env`).
- **Publicar en producción:** ver **`DEPLOY.md`** (Vercel + base Neon).

## Ejecución (Windows / PowerShell o Git Bash)

La contraseña de PostgreSQL se pasa por la variable de entorno `PGPASSWORD`
(no se guarda en ningún archivo). Ajusta la ruta de `psql` si difiere.

```bash
# 0. Credenciales (solo en la sesión actual)
export PGPASSWORD='TU_CONTRASEÑA'
export PGCLIENTENCODING=UTF8
PSQL="/c/Program Files/PostgreSQL/18/bin/psql"

# 1. Crear el esquema (borra y recrea las 6 tablas)
"$PSQL" -h localhost -p 5432 -U postgres -d demoscoring -v ON_ERROR_STOP=1 -f schema.sql

# 2. Generar y cargar los datos (TRUNCATE + COPY; reproducible con SEED=42)
python generate.py

# 3. Verificar (imprime las 14 verificaciones)
"$PSQL" -h localhost -p 5432 -U postgres -d demoscoring -f verify.sql
```

En PowerShell puro, sustituye los `export` por:
```powershell
$env:PGPASSWORD = 'TU_CONTRASEÑA'
$env:PGCLIENTENCODING = 'UTF8'
```

### Reproducibilidad e idempotencia

- `generate.py` fija `random.seed(42)`: la misma corrida produce **exactamente**
  los mismos datos. Para recalibrar, cambia parámetros y vuelve a correrlo.
- Tanto `schema.sql` (`DROP TABLE IF EXISTS ... CASCADE`) como `generate.py`
  (`TRUNCATE ... RESTART IDENTITY CASCADE`) pueden ejecutarse varias veces sin error.
- Variables opcionales para la conexión: `PGHOST`, `PGPORT`, `PGUSER`,
  `PGDATABASE` (por defecto `localhost` / `5432` / `postgres` / `demoscoring`).

## Modelo de datos (llave `codigo_unico`)

```
solicitante (tabla maestra, PK codigo_unico, formato CLI-000001…CLI-025000)
 ├─ validacion       (2 corridas/cliente: Verifiquemos originación + monitoreo)
 ├─ osint_hallazgo   (hallazgos OSINT por corrida)
 ├─ veritas          (análisis crediticio · SOLO créditos)
 ├─ comportamiento   (desenlace real: atrasos, mora, cobro legal, seguro)
 └─ proyeccion_mora  (LSTM: probabilidad de mora a 12m · SOLO créditos)
```

El campo `arquetipo` en `solicitante` es interno (trazabilidad): permite verificar
que cada patrón se sembró donde debía. No se muestra al usuario final del demo.

## Cómo se garantiza la coherencia

- El **score** (`validacion`) es la suma exacta de sus 7 subfactores (V13 = 0).
- La **curva de mora** escala con la banda de score (R1): Bajo < Medio < Medio-alto < Alto.
- La **proyección LSTM** (`proyeccion_mora`) se calcula **al final** como función de
  los demás campos del cliente (R5): atrasos, capacidad de pago VERITAS, banda de
  score, adverse media, deriva entre corridas, PEP/CPE, riesgo geográfico, perfil
  demográfico y edad. Nunca es aleatoria. Reglas duras: D1 (sano) ≤ 15%, C1
  (sobreendeudado) ≥ 50% (V11 = 0). `factores_explicativos` guarda los factores
  que **realmente** pesaron en cada cliente.
- **Integridad referencial** (V14): todo crédito tiene VERITAS y LSTM; ninguna
  tarjeta los tiene.

## Resultado de la verificación

Las **14 verificaciones** de la sección 7 se cumplen (ver `REPORTE_VERIFICACION.txt`).
Resumen de la última corrida:

| # | Verificación | Resultado | Criterio |
|---|---|---|---|
| V1 | Curva de mora por banda | 5.6 → 16.0 → 21.5 → 29.5 %; ratio Alto/Bajo **5.3×** | Creciente, 4–5.5× ✅ |
| V2 | Adverse media predice mora | 35.8 % vs 10.6 % (**3.4×**) | 3–4× ✅ |
| V3 | Biometría baja → default temprano | 21.2 % vs 1.4 % | Mucho mayor ✅ |
| V4 | PEP peligroso (A4) vs inofensivo (E1) | 39.7 % vs 11.0 % | A4 ≫ E1 ✅ |
| V5 | Deterioro por cosecha (score) | 32.6 → 46.0 | ~31 → ~44 ✅ |
| V6 | Crecimiento PEP interanual | 1152 → 1330 → 1480 → 1680 → 1900 | ~10 % ✅ |
| V7 | Pre-cualificados D1 | 4,300 | ~4,300 ✅ |
| V8 | Deteriorado silencioso B4 | 210 | ~210 ✅ |
| V9 | Riesgo medio sin seguro C6 | 3,507 | ~3,200 (±15 %) ✅ |
| V10 | VERITAS predijo la mora | C 33.2 % ≫ A 0.0 % | C ≫ A ✅ |
| V11 | Coherencia LSTM (D1/C1) | 0 y 0 | Cero ✅ |
| V12 | Demográfico de riesgo C4 | 28.2 % vs 14.1 % cartera | Superior ✅ |
| V13 | Integridad del score | 0 errores | Cero ✅ |
| V14 | Integridad referencial | 0 / 0 / 0 / 0 | Cero ✅ |
```
