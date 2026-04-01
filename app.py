import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai

# =======================================================
# MODO NUBE: La llave ahora está oculta y segura
# =======================================================
API_KEY = os.environ.get("GEMINI_API_KEY")

app = Flask(__name__)
CORS(app)

contexto = """
Eres el agente experto de soporte técnico y ciberseguridad de SARD TECH.
Tu objetivo es atender a los visitantes de la página web de forma amable y profesional.
Responde de forma concisa, en español de México. Convence al cliente de que SARD TECH es la mejor opción.
"""

@app.route("/chat", methods=["POST"])
def responder_chat():
    # Verificar que la API Key esté configurada en Render.com
    if not API_KEY:
        return jsonify({"error": "Falta configurar la llave GEMINI_API_KEY en las variables de entorno del servidor"}), 500

    try:
        datos = request.json
        mensaje_cliente = datos.get("mensaje")

        if not mensaje_cliente:
            return jsonify({"error": "No enviaste ningún mensaje"}), 400

        # FIX: también ignorar el ping preventivo del frontend
        if mensaje_cliente.strip().lower() == "ping":
            return jsonify({"respuesta": "ok"}), 200

        cliente_gemini = genai.Client(api_key=API_KEY)

        # FIX 1: Modelo corregido de 'gemini-2.5-flash' (no existe) a 'gemini-2.0-flash'
        # FIX 2: system_instruction separado del mensaje del usuario para que Gemini lo procese correctamente
        respuesta = cliente_gemini.models.generate_content(
            model='gemini-2.0-flash',
            contents=mensaje_cliente,
            config=genai.types.GenerateContentConfig(
                system_instruction=contexto
            )
        )

        texto_respuesta = respuesta.text.replace('*', '')
        return jsonify({"respuesta": texto_respuesta})

    except Exception as e:
        # Imprime el error real en los logs de Render.com para diagnóstico
        print(f"Error en /chat: {e}", flush=True)
        return jsonify({"error": f"Ocurrió un error en el servidor: {str(e)}"}), 500

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)
