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
    if not API_KEY:
        return jsonify({"error": "Falta configurar la llave en el servidor"}), 500

    try:
        datos = request.json
        mensaje_cliente = datos.get("mensaje")
        
        if not mensaje_cliente:
            return jsonify({"error": "No enviaste ningún mensaje"}), 400
            
        cliente_gemini = genai.Client(api_key=API_KEY)
        respuesta = cliente_gemini.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{contexto}\nCliente: {mensaje_cliente}\nAgente SARD TECH:"
        )
        
        texto_respuesta = respuesta.text.replace('*', '') 
        return jsonify({"respuesta": texto_respuesta})
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Ocurrió un error en el servidor"}), 500

if __name__ == "__main__":
    # En la nube, el servidor decide el puerto, por eso usamos os.environ.get
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)