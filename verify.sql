-- =====================================================================
-- VERIFICACIÓN (sección 7 de la especificación) — base demoscoring
-- Ejecuta las 14 verificaciones obligatorias del demo Verifiquemos.
-- =====================================================================
\pset footer off

\echo '=== V1 · Curva de mora monótona por banda (R1) — debe ser CRECIENTE, ratio Alto/Bajo 4-5.5x ==='
SELECT v.banda_score,
       COUNT(*) AS clientes,
       ROUND(100.0 * SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mora
FROM validacion v
JOIN comportamiento c USING (codigo_unico)
WHERE v.numero_corrida = 1
GROUP BY v.banda_score
ORDER BY MIN(v.score_total);

\echo '=== V2 · Adverse media predice mora (~41% vs ~9%) ==='
SELECT CASE WHEN o.codigo_unico IS NOT NULL THEN 'Con adverse media' ELSE 'Sin adverse media' END AS grupo,
       COUNT(*) AS clientes,
       ROUND(100.0 * SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mora
FROM comportamiento c
LEFT JOIN (SELECT DISTINCT codigo_unico FROM osint_hallazgo
           WHERE sentimiento = 'Negativo' AND categoria IN ('Criminal','Noticias','Listas')) o
       USING (codigo_unico)
GROUP BY 1;

\echo '=== V3 · Biometría baja -> mas default temprano (~6x) ==='
SELECT CASE WHEN v.coincidencia_facial < 85 THEN 'Facial < 85' ELSE 'Facial >= 85' END AS grupo,
       COUNT(*) AS clientes,
       ROUND(100.0 * SUM(CASE WHEN c.meses_hasta_mora < 6 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_default_temprano
FROM validacion v JOIN comportamiento c USING (codigo_unico)
WHERE v.numero_corrida = 1
GROUP BY 1;

\echo '=== V4 · PEP peligroso (A4) vs PEP inofensivo (E1) — ~33% vs ~8% ==='
SELECT s.arquetipo, COUNT(*) AS clientes,
       ROUND(100.0 * SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mora
FROM solicitante s JOIN comportamiento c USING (codigo_unico)
WHERE s.arquetipo IN ('A4','E1')
GROUP BY s.arquetipo;

\echo '=== V5 · Deterioro de originación por cosecha (R2): score sube 31 -> 44 ==='
SELECT s.cohorte, ROUND(AVG(v.score_total),1) AS score_promedio, COUNT(*) AS clientes
FROM solicitante s JOIN validacion v USING (codigo_unico)
WHERE v.numero_corrida = 1
GROUP BY s.cohorte ORDER BY s.cohorte;

\echo '=== V6 · Crecimiento PEP ~10% interanual (R3) ==='
SELECT s.cohorte, COUNT(*) AS pep_con_credito
FROM solicitante s JOIN validacion v USING (codigo_unico)
WHERE v.numero_corrida = 1 AND v.pep = TRUE
  AND s.tipo_producto IN ('Crédito Consumo','Crédito Pyme')
GROUP BY s.cohorte ORDER BY s.cohorte;

\echo '=== V7 · Segmento pre-cualificado D1 (~4,300) ==='
SELECT COUNT(*) AS d1_clientes FROM solicitante WHERE arquetipo = 'D1';

\echo '=== V8 · Deteriorado silencioso B4 (~210, limpios al inicio pero LSTM > 65%) ==='
SELECT COUNT(*) AS b4_detectados FROM solicitante s
JOIN validacion v1 ON v1.codigo_unico = s.codigo_unico AND v1.numero_corrida = 1
JOIN proyeccion_mora p ON p.codigo_unico = s.codigo_unico
WHERE v1.banda_score = 'Bajo' AND p.probabilidad_mora > 65;

\echo '=== V9 · Riesgo medio sin seguro C6 (~3,200) ==='
SELECT COUNT(*) AS medio_sin_seguro FROM comportamiento c JOIN proyeccion_mora p USING (codigo_unico)
WHERE c.tiene_seguro_vida_credito = FALSE AND p.nivel_riesgo = 'Medio';

\echo '=== V10 · VERITAS predijo la mora (C ~38% vs A ~6%) ==='
SELECT ve.comportamiento_pago, COUNT(*) AS clientes,
       ROUND(100.0 * SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mora
FROM veritas ve JOIN comportamiento c USING (codigo_unico)
GROUP BY ve.comportamiento_pago ORDER BY ve.comportamiento_pago;

\echo '=== V11 · Coherencia LSTM (R5) — AMBOS deben dar 0 ==='
SELECT 'INCOHERENCIA: D1 con prob alta' AS problema, COUNT(*) AS n
FROM solicitante s JOIN proyeccion_mora p USING (codigo_unico)
WHERE s.arquetipo = 'D1' AND p.probabilidad_mora > 15
UNION ALL
SELECT 'INCOHERENCIA: C1 con prob baja', COUNT(*)
FROM solicitante s JOIN proyeccion_mora p USING (codigo_unico)
WHERE s.arquetipo = 'C1' AND p.probabilidad_mora < 50;

\echo '=== V12 · Perfil demográfico de riesgo C4 (soltero joven Noroccidente) ==='
SELECT ROUND(100.0 * SUM(CASE WHEN c.en_mora THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mora,
       COUNT(*) AS clientes
FROM solicitante s JOIN comportamiento c USING (codigo_unico)
WHERE s.estado_civil = 'Soltero' AND s.edad BETWEEN 18 AND 30
  AND s.region = 'Noroccidente' AND s.tipo_producto = 'Crédito Consumo';

\echo '=== V12b · Mora promedio de toda la cartera (referencia para V12) ==='
SELECT ROUND(100.0 * AVG(CASE WHEN en_mora THEN 1 ELSE 0 END), 1) AS pct_mora_cartera FROM comportamiento;

\echo '=== V13 · Integridad del score: suma de subfactores = score_total (DEBE dar 0) ==='
SELECT COUNT(*) AS errores_score FROM validacion
WHERE score_total <> (sub_identidad_listas + sub_riesgo_geografico + sub_perfil_ingresos
                    + sub_actividad_economica + sub_condicion_especial
                    + sub_naturaleza_cliente + sub_producto_servicio);

\echo '=== V14 · Integridad referencial: crédito tiene VERITAS y LSTM; tarjeta NO (AMBOS 0) ==='
SELECT 'Créditos sin VERITAS' AS problema, COUNT(*) AS n
FROM solicitante s LEFT JOIN veritas v USING (codigo_unico)
WHERE s.tipo_producto <> 'Tarjeta de Crédito' AND v.codigo_unico IS NULL
UNION ALL
SELECT 'Créditos sin LSTM', COUNT(*)
FROM solicitante s LEFT JOIN proyeccion_mora p USING (codigo_unico)
WHERE s.tipo_producto <> 'Tarjeta de Crédito' AND p.codigo_unico IS NULL
UNION ALL
SELECT 'Tarjetas CON VERITAS (no debería)', COUNT(*)
FROM solicitante s JOIN veritas v USING (codigo_unico)
WHERE s.tipo_producto = 'Tarjeta de Crédito'
UNION ALL
SELECT 'Tarjetas CON LSTM (no debería)', COUNT(*)
FROM solicitante s JOIN proyeccion_mora p USING (codigo_unico)
WHERE s.tipo_producto = 'Tarjeta de Crédito';
