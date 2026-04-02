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
# CONTEXTO DEL BOT
# ─────────────────────────────────────────
CONTEXTO = (
    "Eres el agente experto de soporte técnico y ciberseguridad de SARD TECH. "
    "Tu objetivo es atender a los visitantes de la página web de forma amable y profesional. "
    "Responde de forma concisa, en español de México. "
    "Convence al cliente de que SARD TECH es la mejor opción."
)

# ─────────────────────────────────────────
# FUNCIÓN: GUARDAR MENSAJE EN SUPABASE
# ─────────────────────────────────────────
def guardar_mensaje(rol: str, contenido: str):
    try:
        supabase.table("chats_sardtech").insert({
            "rol":       rol,
            "mensaje":   contenido,
            "creado_en": datetime.utcnow().isoformat()
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

        if not mensaje_cliente:
            return jsonify({"error": "Mensaje vacio"}), 400

        if mensaje_cliente.lower() == "ping":
            return jsonify({"respuesta": "ok"}), 200

        # 1️⃣ Guardar mensaje del USUARIO en Supabase
        guardar_mensaje("user", mensaje_cliente)

        # 2️⃣ Llamar a Claude (Anthropic)
        cliente   = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        respuesta = cliente.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            system=CONTEXTO,
            messages=[
                {"role": "user", "content": mensaje_cliente}
            ]
        )
        texto = respuesta.content[0].text.strip()

        # 3️⃣ Guardar respuesta del BOT en Supabase
        guardar_mensaje("assistant", texto)

        # 4️⃣ Devolver respuesta al cliente
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
