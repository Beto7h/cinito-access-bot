import os
import time
import telebot
import threading
from telebot import types
from pymongo import MongoClient # Necesitas instalar: pip install pymongo dnspython
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURACIÓN DE VARIABLES ---
TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI') # Guarda aquí tu link de MongoDB Atlas
API_KEY_GPLINKS = os.getenv('GPLINKS_API')
GRUPO_ID = int(os.getenv('GRUPO_ID'))
BOT_USERNAME = os.getenv('BOT_USERNAME')
ADMIN_ID = 7523334989 

bot = telebot.TeleBot(TOKEN)

# --- CONEXIÓN A MONGODB ---
client = MongoClient(MONGO_URI)
db = client['cinito_bot']
links_col = db['links']  # Colección para los enlaces de los usuarios
stats_col = db['stats']  # Colección para las ventas

# --- SERVIDOR PARA KOYEB ---
class MockServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Cinito Bot Online")

def run_mock_server():
    server = HTTPServer(('0.0.0.0', 8060), MockServer)
    server.serve_forever()

# --- FUNCIÓN MAESTRA DE ENTREGA ---
def entregar_acceso(chat_id, user_id, dias, usos, nombre_plan, tipo="vip"):
    try:
        segundos = dias * 86400
        invite = bot.create_chat_invite_link(GRUPO_ID, member_limit=usos, expire_date=int(time.time()) + segundos)
        
        # 💾 GUARDADO EN MONGODB (Se sobreescribe si ya existe uno)
        links_col.update_one(
            {"user_id": user_id},
            {"$set": {
                "link": invite.invite_link,
                "expira": time.time() + segundos,
                "tipo": tipo,
                "plan": nombre_plan
            }},
            upsert=True
        )
        
        texto = (
            f"<b>✅ ¡{nombre_plan} Activado!</b>\n\n"
            f"Tu enlace de unión es:\n👉 {invite.invite_link}\n\n"
            f"<i>Este link se guardó en tu historial por {dias} día(s).</i>"
        )
        bot.send_message(chat_id, texto, parse_mode="HTML", disable_web_page_preview=True)

        # Notificación al Admin
        bot.send_message(ADMIN_ID, f"📢 <b>NUEVO ACCESO</b>\n👤 ID: <code>{user_id}</code>\n🎫 Plan: {nombre_plan}", parse_mode="HTML")

    except Exception as e:
        bot.send_message(chat_id, "❌ Error al generar el acceso en el grupo.")

# --- LÓGICA DE HISTORIAL ---
def gestionar_historial(chat_id, user_id):
    ahora = time.time()
    # 🔍 BUSCAMOS EN MONGODB
    data = links_col.find_one({"user_id": user_id})

    if data:
        if ahora < data['expira']:
            bot.send_message(
                chat_id, 
                f"<b>📂 TU ENLACE ACTUAL:</b>\n\n👉 {data['link']}\n\n<i>Válido por el tiempo restante de tu plan.</i>", 
                parse_mode="HTML", 
                disable_web_page_preview=True
            )
        else:
            links_col.delete_one({"user_id": user_id})
            bot.send_message(chat_id, "❌ Tu enlace ha expirado.")
    else:
        bot.send_message(chat_id, "🧐 No tienes enlaces activos en este momento.")

# --- COMANDOS ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    params = message.text.split()

    if len(params) > 1 and params[1] == 'verificado':
        entregar_acceso(message.chat.id, user_id, 1, 1, "Acceso Gratuito", "free")
    else:
        # TU MENSAJE DE BIENVENIDA ORIGINAL
        texto_bienvenida = (
            f"<b>🎬 ¡BIENVENIDO A CINITO VIP!</b>\n\n"
            f"Hola <b>{message.from_user.first_name}</b>, elige cómo obtener tu acceso:\n\n"
            f"----------------------------------\n"
            f"<b>🆓 OPCIÓN GRATUITA</b>\n"
            f"Completa el acortador para recibir tu link.\n"
            f"👉 <i>Usa el botón 'Acceso Gratis'.</i>\n\n"
            f"----------------------------------\n"
            f"<b>⭐ PASES RÁPIDOS (VIP)</b>\n"
            f"Entra al instante sin anuncios usando <b>Telegram Stars</b>:\n\n"
            f"🔹 <b>Plan Básico (1⭐):</b> 24h / 1 uso\n"
            f"🔹 <b>Plan VIP (8⭐):</b> 15 días / 10 usos\n\n"
            f"<b>¿Qué prefieres hacer hoy?</b> 👇"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🆓 Acceso Gratis (Acortador)", callback_data="intentar_generar"),
            types.InlineKeyboardButton("⭐ Plan Básico (1⭐)", callback_data="buy_p1"),
            types.InlineKeyboardButton("📂 Mis Enlaces", callback_data="ver_historial")
        )
        bot.send_message(message.chat.id, texto_bienvenida, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    uid = call.from_user.id
    if call.data == "ver_historial":
        bot.answer_callback_query(call.id)
        gestionar_historial(call.message.chat.id, uid)
    
    elif call.data == "intentar_generar":
        bot.answer_callback_query(call.id)
        url = f"https://gplinks.in/st?api={API_KEY_GPLINKS}&url=https://t.me/{BOT_USERNAME}?start=verificado"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🚀 Ir al Acortador", url=url))
        bot.send_message(call.message.chat.id, "<b>🔓 Acceso Gratis</b>\nCompleta el acortador:", parse_mode="HTML", reply_markup=markup)

    elif call.data == "buy_p1":
        bot.answer_callback_query(call.id)
        bot.send_invoice(call.message.chat.id, title="Plan Básico", description="Acceso VIP 24h", invoice_payload="pay_p1", provider_token="", currency="XTR", prices=[types.LabeledPrice(label="VIP", amount=1)])

# --- PAGOS ---
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    entregar_acceso(message.chat.id, message.from_user.id, 1, 1, "Plan Básico", "vip")

if __name__ == "__main__":
    threading.Thread(target=run_mock_server, daemon=True).start()
    bot.infinity_polling()
