import os
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
from supabase import create_client, Client
from datetime import datetime

# ─────────────────────────────────────────
# VARIABLES DE ENTORNO
# ─────────────────────────────────────────
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY")
SUPABASE_URL   = os.environ.get("SUPABASE_URL")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

# ─────────────────────────────────────────
# INICIALIZAR FLASK Y SUPABASE
# ─────────────────────────────────────────
app = Flask(__name__)
CORS(app)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────
# MEMORIA DE CONVERSACIONES
# ─────────────────────────────────────────
historial_sesiones = {}
leads_registrados  = {}

# ─────────────────────────────────────────
# PROMPT KIRA
# ─────────────────────────────────────────
CONTEXTO = """
Eres KIRA, la asesora de Ciberseguridad IA de SARD TECH. Tu objetivo real es hacer
Product Discovery y perfilar al cliente, pero ante el usuario estás haciendo
un diagnóstico de seguridad completamente gratuito.

REGLAS ESTRICTAS:
1. Sé conversacional y empática. JAMÁS hagas más de UNA pregunta por mensaje.
   Si tienes varias preguntas en mente, elige SOLO la más importante.
   Reacciona primero a lo que el cliente dijo, luego haz tu UNA pregunta.

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

5. EL CIERRE: Cuando el cliente responda la pregunta de oro, dile EXACTAMENTE:
   "Tengo un diagnóstico preliminar listo para ti con los puntos ciegos que detecté.
   Por favor, escríbeme tu correo electrónico y el nombre de tu empresa para
   enviártelo y que un consultor experto de SARD TECH se ponga en contacto contigo."

6. Responde siempre en español de México, conciso y profesional.
   Sin asteriscos ni markdown. Adapta tu lenguaje al perfil del cliente.
"""

# ─────────────────────────────────────────
# DETECTAR EMAIL
# ─────────────────────────────────────────
def detectar_email(texto):
    patron = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(patron, texto)
    return match.group(0) if match else None

# ─────────────────────────────────────────
# GUARDAR EN SUPABASE
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
        print(f"[Supabase] Error: {e}", flush=True)

# ─────────────────────────────────────────
# GENERAR REPORTE HTML
# ─────────────────────────────────────────
def generar_reporte(historial, empresa, email_cliente):
    cliente = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    conversacion = "\n".join([
        f"{'Cliente' if m['role']=='user' else 'KIRA'}: {m['content']}"
        for m in historial
    ])
    prompt = f"""
Basándote en esta conversación de auditoría, genera un reporte profesional HTML
para la empresa "{empresa}" (correo: {email_cliente}).

CONVERSACIÓN:
{conversacion}

Genera HTML profesional con estilos inline (fondo blanco, tipografía limpia) con:
1. ENCABEZADO: SARD TECH, título, fecha, nombre empresa
2. RESUMEN EJECUTIVO: 2-3 oraciones del perfil detectado
3. VULNERABILIDADES: 3-5 riesgos con nivel ALTO/MEDIO/BAJO en colores
4. PERFIL: Tabla con datos recopilados
5. PLAN INMEDIATO: 3 acciones sin costo para hoy
6. PRÓXIMOS PASOS: Cómo SARD TECH puede ayudar
7. PIE: contacto@sardtech.com.mx · sardtech.com.mx

Colores: fondo blanco, acentos #00b8d4, texto #1a1a2e. Todo en español de México.
Devuelve SOLO el HTML, sin explicaciones.
"""
    resp = cliente.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text.strip()

# ─────────────────────────────────────────
# ENVIAR CORREO CON RESEND
# ─────────────────────────────────────────
def enviar_reporte_resend(email_destino, empresa, historial):
    import threading
    def _enviar():
        try:
            reporte_html = generar_reporte(historial, empresa, email_destino)
            # Limpiar etiquetas de markdown
            reporte_html = reporte_html.replace("```html", "").replace("```", "").strip()
            html_correo = f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">
  <div style="max-width:680px;margin:30px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
    <div style="background:#080c10;padding:30px 40px;text-align:center;">
      <h1 style="color:#00e5ff;font-size:28px;margin:0;letter-spacing:3px;">SARD TECH</h1>
      <p style="color:#7d8590;font-size:12px;margin:6px 0 0;letter-spacing:2px;">// CYBERSECURITY AI PLATFORM · KIRA</p>
    </div>
    <div style="padding:36px 40px 20px;">
      <h2 style="color:#080c10;font-size:22px;margin:0 0 14px;">Tu diagnóstico está listo, {empresa}</h2>
      <p style="color:#555;font-size:15px;line-height:1.7;margin:0 0 16px;">
        Gracias por completar tu auditoría con KIRA. Hemos preparado un reporte
        personalizado con los puntos ciegos detectados en tu operación.
      </p>
      <p style="color:#555;font-size:15px;line-height:1.7;margin:0;">
        Un consultor de SARD TECH se pondrá en contacto en las próximas 24 horas.
      </p>
    </div>
    <div style="height:2px;background:linear-gradient(90deg,#00e5ff,transparent);margin:0 40px;"></div>
    <div style="padding:24px 40px 36px;">
      <h3 style="color:#080c10;font-size:16px;margin:0 0 20px;text-transform:uppercase;letter-spacing:1px;">📋 Tu Reporte de Diagnóstico</h3>
      {reporte_html}
    </div>
    <div style="background:#f8f9fa;padding:28px 40px;text-align:center;border-top:1px solid #eee;">
      <a href="https://wa.me/525633212240" style="display:inline-block;background:#25D366;color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px;margin-right:10px;">WhatsApp</a>
      <a href="mailto:contacto@sardtech.com.mx" style="display:inline-block;background:#080c10;color:#00e5ff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px;">Correo</a>
    </div>
    <div style="background:#080c10;padding:20px 40px;text-align:center;">
      <p style="color:#7d8590;font-size:12px;margin:0;">© 2026 SARD TECH · contacto@sardtech.com.mx · sardtech.com.mx</p>
    </div>
  </div>
</body>
</html>"""
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": "KIRA · SARD TECH <contacto@sardtech.com.mx>",
                    "to": [email_destino, "contacto@sardtech.com.mx"],
                    "subject": "🛡️ Tu Diagnóstico de Ciberseguridad — SARD TECH",
                    "html": html_correo
                }
            )
            if response.status_code == 200:
                print(f"[Resend] Correo enviado a {email_destino} ✅", flush=True)
            else:
                print(f"[Resend] Error: {response.text}", flush=True)
        except Exception as e:
            print(f"[Resend] Error: {e}", flush=True)

    threading.Thread(target=_enviar, daemon=True).start()

# ─────────────────────────────────────────
# RUTA: HEALTH CHECK
# ─────────────────────────────────────────
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "SARD TECH Bot activo — KIRA online"}), 200

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

        if session_id not in historial_sesiones:
            historial_sesiones[session_id] = []

        historial_sesiones[session_id].append({"role": "user", "content": mensaje_cliente})
        guardar_mensaje(session_id, "user", mensaje_cliente)

        cliente   = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        respuesta = cliente.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            system=CONTEXTO,
            messages=historial_sesiones[session_id]
        )
        texto = respuesta.content[0].text.strip()

        historial_sesiones[session_id].append({"role": "assistant", "content": texto})
        guardar_mensaje(session_id, "assistant", texto)

        # Detectar lead y enviar reporte
        lead_capturado = False
        email_detectado = detectar_email(mensaje_cliente)

        if email_detectado and session_id not in leads_registrados:
            leads_registrados[session_id] = True
            partes  = mensaje_cliente.split(',')
            empresa = partes[1].strip() if len(partes) > 1 else "tu empresa"

            try:
                supabase.table("chats_sardtech").insert({
                    "session_id": session_id,
                    "rol":        "lead",
                    "mensaje":    f"EMAIL: {email_detectado} | EMPRESA: {empresa}",
                    "creado_en":  datetime.utcnow().isoformat()
                }).execute()
            except Exception as e:
                print(f"[Lead] Error: {e}", flush=True)

            if RESEND_API_KEY:
                enviar_reporte_resend(email_detectado, empresa, historial_sesiones[session_id].copy())
                lead_capturado = True

        return jsonify({"respuesta": texto, "reporte_enviado": lead_capturado}), 200

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────
# ARRANCAR SERVIDOR
# ─────────────────────────────────────────
if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)
