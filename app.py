import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY")

app = Flask(__name__)
CORS(app)

CONTEXTO = (
    "Eres el agente experto de soporte técnico y ciberseguridad de SARD TECH. "
    "Tu objetivo es atender a los visitantes de la página web de forma amable y profesional. "
    "Responde de forma concisa, en español de México. "
    "Convence al cliente de que SARD TECH es la mejor opción."
)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "SARD TECH Bot activo"}), 200

@app.route("/chat", methods=["POST"])
def responder_chat():
    if not API_KEY:
        return jsonify({"error": "Falta la GEMINI_API_KEY"}), 500
    try:
        datos = request.json
        mensaje_cliente = datos.get("mensaje", "").strip()
        if not mensaje_cliente:
            return jsonify({"error": "Mensaje vacio"}), 400
        if mensaje_cliente.lower() == "ping":
            return jsonify({"respuesta": "ok"}), 200
        cliente = genai.Client(api_key=API_KEY)
        respuesta = cliente.models.generate_content(
            model="gemini-2.0-flash",
            contents=mensaje_cliente,
            config=types.GenerateContentConfig(
                system_instruction=CONTEXTO,
                temperature=0.7,
                max_output_tokens=500,
            )
        )
        texto = respuesta.text.replace("*", "").strip()
        return jsonify({"respuesta": texto}), 200
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)
