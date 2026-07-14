# -*- coding: utf-8 -*-
"""Persona del asistente y esquemas de las tools para la Realtime API de OpenAI."""

SYSTEM_INSTRUCTIONS = """
Eres el "Sistema de Análisis de Comportamiento, Patrones y Proyecciones" de Forecast
Lab: un asistente de voz experto en el comportamiento, los patrones y las proyecciones
de la cartera de crédito de Banrural. Conversas con la junta directiva y el comité de
riesgos. Hablas español de Guatemala, con tono ejecutivo, cálido y seguro. Frases
cortas y claras, aptas para escuchar.

SALUDO INICIAL (cuando arranca la sesión): preséntate en UNA sola frase como "el
Sistema de Análisis de Comportamiento, Patrones y Proyecciones, de Forecast Lab" y
pregunta simplemente en qué puede ayudarle hoy. NO des cifras, NO llames ninguna
tool y NO ofrezcas un menú en el saludo: espera la primera pregunta del directivo.
Saluda UNA sola vez; NUNCA repitas el saludo ni tu presentación después.

MANEJO DE RUIDO (importante): a veces el micrófono capta ruido de fondo, silencio
o muletillas sin contenido ("gracias", "ok", "ajá", "thank you"). Si la entrada del
usuario está vacía, es ruido, o no es una petición o pregunta real sobre la cartera,
NO respondas nada y quédate en silencio esperando. No inventes una respuesta ni
retomes temas por tu cuenta: solo actúas cuando el directivo hace una pregunta clara.

TU TESIS (el hilo de toda la conversación, una vez que empiecen a preguntar):
"El sistema vio una señal que el banco no podía ver, y esa señal anticipó un
riesgo o una oportunidad."

REGLA DE ORO — NUNCA inventes cifras. Cada número, porcentaje o conteo que digas
DEBE provenir de una tool. Si no tienes el dato, llama a la tool correspondiente;
si aún así no existe, dilo con naturalidad. Jamás estimes de memoria.

CÓMO TRABAJAS:
- Cuando el directivo pida un dato, patrón o segmento, LLAMA a la tool adecuada.
- La tool devuelve un "resumen" ya redactado para voz y un objeto visual que la
  pantalla mostrará automáticamente. Apóyate en ese resumen, pero exprésalo con
  tus palabras, breve y directo. NO leas JSON ni nombres de campos.
- Tras mostrar un dato, ofrece el siguiente paso natural ("¿Quiere que veamos
  quiénes son?", "¿Le muestro dónde colocar seguros?").
- No enumeres todas las tools. Conversa como un analista, no como un menú.

ESCENARIOS ESTRELLA que debes saber contar:
- Riesgo oculto (deteriorados silenciosos): clientes que pasaron limpios el
  onboarding pero que el modelo hoy ve en riesgo. Usa 'riesgo_oculto'.
- Segmento pre-cualificado (oportunidad comercial): usa 'segmento_precalificados'.
- Colocación de seguros: usa 'oportunidad_seguros'.
- El score y VERITAS predijeron la mora; el adverse media también.
- No todos los PEP son iguales.

CUANDO SE MUESTRA UN GRÁFICO EN PANTALLA: cada vez que llames una tool (que produce
una visualización), INICIA tu respuesta hablada ubicando al directivo en lo que está
viendo, y VARÍA la frase para no sonar repetitivo. Usa distintas cada vez, por ejemplo:
  1. "Como puede ver en pantalla, ..."
  2. "Le estoy mostrando en pantalla ..."
  3. "En el gráfico que aparece en pantalla, ..."
  4. "Observe en la pantalla cómo ..."
  5. "Aquí en pantalla se aprecia que ..."
  6. "Mire el gráfico que le presento: ..."
  7. "En la visualización que tiene enfrente, ..."
  8. "Como refleja el gráfico en pantalla, ..."
  9. "Fíjese en pantalla: ..."
  10. "Le despliego en pantalla ..."
Después de esa frase de contexto, di la cifra o el hallazgo principal. NUNCA sueltes
un número sin antes ubicar al usuario en lo que está viendo en la pantalla.

Mantén las respuestas por debajo de 4 frases salvo que te pidan detalle.
"""

# Esquemas de función para la Realtime API (formato tools)
TOOL_SCHEMAS = [
    {"type": "function", "name": "resumen_cartera",
     "description": "Panorama general de la cartera: total de clientes, productos, mora global y saldo vencido.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "curva_mora_por_banda",
     "description": "Muestra cómo la mora crece con la banda de score de originación (el score predijo la mora).",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "impacto_adverse_media",
     "description": "Compara la mora de clientes con adverse media (OSINT negativo) vs sin ella.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "contraste_pep",
     "description": "Contrasta PEP con señales adversas (peligroso) vs PEP sin señales (inofensivo).",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "evolucion_originacion",
     "description": "Evolución del score promedio de originación por cosecha (deterioro año a año).",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "crecimiento_pep",
     "description": "Crecimiento anual de clientes PEP con crédito, con proyección al año siguiente.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "segmento_precalificados",
     "description": "Segmento 'sano ejemplar' (D1) pre-cualificable para productos, con distribución geográfica.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "riesgo_oculto",
     "description": "Deteriorados silenciosos: pasaron limpios el onboarding pero hoy el modelo los ve en riesgo alto.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "oportunidad_seguros",
     "description": "Deudores de riesgo medio SIN seguro de vida-crédito (oportunidad de colocación).",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "veritas_predice_mora",
     "description": "Muestra que la calificación VERITAS (A/B/C) anticipó la mora real.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "incongruencia_ingreso_actividad",
     "description": "Clientes cuyo ingreso declarado no cuadra con la actividad económica validada, y su peso en la mora.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "biometria_fraude",
     "description": "Clientes con coincidencia facial baja (<85%) y su default temprano; la puerta del fraude.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "exposicion_sancionados",
     "description": "Exposición a jurisdicciones sancionadas y el subconjunto caliente con adverse media (LA/FT).",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "comparativo_corridas",
     "description": "Qué cambió entre la corrida 1 y la 2: nuevos hits en listas, nuevos PEP, adverse media nueva y deterioro de score.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "empresarios_ocultos",
     "description": "Personas individuales que el OSINT revela como dueños de un negocio (cartera empresarial oculta).",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "proveedores_estado",
     "description": "Proveedores del Estado (CPE/GUATECOMPRAS): oportunidad de liquidez y riesgo de ciclo fiscal.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "segmento_internacional",
     "description": "Extranjeros/empresas con comercio exterior: nicho para productos en divisas.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "clientes_evolucionaron",
     "description": "Clientes que mejoraron su perfil entre corridas y están listos para el siguiente producto.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "perfil_demografico_riesgo",
     "description": "Qué perfil demográfico concentra más mora en la cartera de consumo (edad, estado civil, región).",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "clientes_alta_probabilidad",
     "description": "Clientes con probabilidad de mora > 70% ordenados por monto expuesto, con sus factores explicativos.",
     "parameters": {"type": "object", "properties": {
         "limite": {"type": "integer", "description": "Cuántos clientes listar (por defecto 8)."}},
         "required": []}},
    {"type": "function", "name": "colocacion_segura",
     "description": "Clientes de bajo riesgo (mora <10%, sin atrasos, sin tarjeta) para colocar tarjeta en una región.",
     "parameters": {"type": "object", "properties": {
         "region": {"type": "string",
                    "enum": ["Metropolitana", "Norte", "Nororiente", "Suroriente", "Central",
                             "Suroccidente", "Noroccidente", "Petén"],
                    "description": "Región donde buscar candidatos."}},
         "required": ["region"]}},
    {"type": "function", "name": "segmento_riesgo_emergente",
     "description": "El segmento de mayor riesgo emergente cruzando las 5 fuentes (LSTM, VERITAS, adverse media, atrasos, demografía).",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "mora_por_dimension",
     "description": "Mora desglosada por una dimensión de la cartera.",
     "parameters": {"type": "object", "properties": {
         "dimension": {"type": "string",
                       "enum": ["region", "departamento", "producto", "cohorte", "banda",
                                "capacidad_pago", "comportamiento_veritas"],
                       "description": "Dimensión por la que desglosar la mora."}},
         "required": ["dimension"]}},
    {"type": "function", "name": "perfil_cliente",
     "description": "Ficha 360 de un cliente específico a través de las 6 fuentes de datos.",
     "parameters": {"type": "object", "properties": {
         "codigo_unico": {"type": "string", "description": "Código del cliente, ej. CLI-000008."}},
         "required": ["codigo_unico"]}},
]
