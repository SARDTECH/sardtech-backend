import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
from supabase import create_client, Client
from datetime import datetime

# ─────────────────────────────────────────
# VARIABLES DE ENTORNO
# ─────────────────────────────────────────
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
SUPABASE_URL  = os.environ.get("SUPABASE_URL")
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY")

# ─────────────────────────────────────────
# INICIALIZAR FLASK
# ─────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────
# INICIALIZAR SUPABASE
# ─────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────
# MEMORIA DE CONVERSACIONES (por sesión)
# ─────────────────────────────────────────
historial_sesiones = {}

# ─────────────────────────────────────────
# PROMPT DE PRODUCT DISCOVERY (limpio, sin mensaje del usuario)
# ─────────────────────────────────────────
CONTEXTO = """
Eres el Auditor de Ciberseguridad IA de SARD TECH. Tu objetivo real es hacer 
Product Discovery y perfilar al cliente, pero ante el usuario estás haciendo 
un diagnóstico de seguridad completamente gratuito.

REGLAS ESTRICTAS:
1. Sé conversacional y empático. NO lances una lista de preguntas. 
   Haz UNA sola pregunta a la vez y reacciona a lo que el cliente te diga.

2. A lo largo de la conversación, DEBES averiguar esta información de forma natural:
   - ¿Cuántos empleados tienen?
   - ¿Tienen un área de TI dedicada o la tecnología la maneja el dueño/gerente?
   - ¿Qué herramientas usan todos los días? (ej. WhatsApp, Google Drive, correos gratuitos)
   - ¿Han tenido algún susto o incidente de seguridad en el pasado?

3. NUNCA repitas una pregunta que ya hiciste en esta conversación.
   Usa las respuestas anteriores para contextualizar las siguientes preguntas.

4. LA PREGUNTA DE ORO: Cuando ya tengas una idea de cómo operan, hazle 
   obligatoriamente esta pregunta exacta:
   "Para terminar de armar tu perfil, dime en una frase: ¿cuál es tu mayor 
   miedo relacionado con la tecnología o la seguridad de tu empresa?"

5. EL CIERRE (CAPTURA DE LEAD): Cuando el cliente responda la pregunta de oro, 
   felicítalo por tomar acción y dile EXACTAMENTE esto:
   "Tengo un diagnóstico preliminar listo para ti con los puntos ciegos que detecté. 
   Por favor, escríbeme tu correo electrónico y el nombre de tu empresa para 
   enviártelo y que un consultor experto de SARD TECH se ponga en contacto contigo."

6. Responde siempre en español de México, de forma concisa y profesional.
"""

# ─────────────────────────────────────────
# FUNCIÓN: GUARDAR MENSAJE EN SUPABASE
# ─────────────────────────────────────────
def guardar_mensaje(session_id: str, rol: str, contenido: str):
    try:
        supabase.table("chats_sardtech").insert({
            "session_id": session_id,
            "rol":        rol,
            "mensaje":    contenido,
            "creado_en":  datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"[Supabase] Error al guardar: {e}", flush=True)

# ─────────────────────────────────────────
# RUTA: HEALTH CHECK
# ─────────────────────────────────────────
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "SARD TECH Bot activo"}), 200

# ─────────────────────────────────────────
# RUTA: CHAT
# ─────────────────────────────────────────
@app.route("/chat", methods=["POST"])
def responder_chat():
    if not ANTHROPIC_KEY:
        return jsonify({"error": "Falta la ANTHROPIC_API_KEY"}), 500

    try:
        datos           = request.json
        mensaje_cliente = datos.get("mensaje", "").strip()
        session_id      = datos.get("session_id", "anonimo")

        if not mensaje_cliente:
            return jsonify({"error": "Mensaje vacio"}), 400

        if mensaje_cliente.lower() == "ping":
            return jsonify({"respuesta": "ok"}), 200

        # 1️⃣ Recuperar o crear historial de esta sesión
        if session_id not in historial_sesiones:
            historial_sesiones[session_id] = []

        # 2️⃣ Agregar mensaje del usuario al historial
        historial_sesiones[session_id].append({
            "role":    "user",
            "content": mensaje_cliente
        })

        # 3️⃣ Guardar mensaje del USUARIO en Supabase
        guardar_mensaje(session_id, "user", mensaje_cliente)

        # 4️⃣ Llamar a Claude con historial completo
        cliente   = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        respuesta = cliente.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            system=CONTEXTO,
            messages=historial_sesiones[session_id]  # ← historial completo
        )
        texto = respuesta.content[0].text.strip()

        # 5️⃣ Agregar respuesta del bot al historial
        historial_sesiones[session_id].append({
            "role":    "assistant",
            "content": texto
        })

        # 6️⃣ Guardar respuesta del BOT en Supabase
        guardar_mensaje(session_id, "assistant", texto)

        # 7️⃣ Devolver respuesta al cliente
        return jsonify({"respuesta": texto}), 200

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────
# ARRANCAR SERVIDOR
# ─────────────────────────────────────────
if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)
