import os
import time
import telebot
import threading
from telebot import types
from pymongo import MongoClient
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURACIÓN DE VARIABLES ---
TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI') # Tu link de MongoDB Atlas
API_KEY_GPLINKS = os.getenv('GPLINKS_API')
GRUPO_ID = int(os.getenv('GRUPO_ID'))
BOT_USERNAME = os.getenv('BOT_USERNAME')
CANAL_TUTORIAL = os.getenv('CANAL_TUTORIAL', 'https://t.me/')

# Tu ID para reportes y avisos:
ADMIN_ID = 7523334989 

bot = telebot.TeleBot(TOKEN)

# --- CONEXIÓN A MONGODB ---
client = MongoClient(MONGO_URI)
db = client['cinito_bot']
links_col = db['links']  # Colección para persistencia de enlaces

# --- SERVIDOR PARA KOYEB ---
class MockServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Cinito VIP Online - Servidor Activo")

def run_mock_server():
    server = HTTPServer(('0.0.0.0', 8060), MockServer)
    server.serve_forever()

# --- MENÚ PRINCIPAL ---
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🆓 Acceso Gratis (Acortador)", callback_data="intentar_generar"),
        types.InlineKeyboardButton("⭐ Plan Básico (1⭐) - 24h / 1 Uso", callback_data="buy_p1"),
        types.InlineKeyboardButton("⭐ Plan Estándar (3⭐) - 3 Días / 4 Usos", callback_data="buy_p3"),
        types.InlineKeyboardButton("⭐ Plan VIP (8⭐) - 15 Días / 10 Usos", callback_data="buy_p8"),
        types.InlineKeyboardButton("📂 Mis Enlaces", callback_data="ver_historial"),
        types.InlineKeyboardButton("❓ Ayuda / Tutorial", callback_data="ver_help")
    )
    return markup

# --- FUNCIÓN DE ENTREGA (Persistencia Total) ---
def entregar_acceso(chat_id, user_id, dias, usos, nombre_plan, tipo="vip"):
    try:
        segundos = dias * 86400
        invite = bot.create_chat_invite_link(GRUPO_ID, member_limit=usos, expire_date=int(time.time()) + segundos)
        
        # 💾 GUARDADO EN MONGODB (Eterno hasta que expire)
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

        # 🔔 Notificación al Admin
        bot.send_message(ADMIN_ID, f"📢 <b>NUEVO ACCESO</b>\n👤 ID: <code>{user_id}</code>\n🎫 Plan: {nombre_plan}\n🔗 {invite.invite_link}", parse_mode="HTML")

    except Exception as e:
        bot.send_message(chat_id, "❌ Error al generar el acceso. Revisa los permisos del bot en el grupo.")

# --- LÓGICA DE HISTORIAL ---
def gestionar_historial(chat_id, user_id):
    ahora = time.time()
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
            f"🔹 <b>Plan Estándar (3⭐):</b> 3 días / 4 usos\n"
            f"🔹 <b>Plan VIP (8⭐):</b> 15 días / 10 usos\n\n"
            f"<b>¿Qué prefieres hacer hoy?</b> 👇"
        )
        bot.send_message(message.chat.id, texto_bienvenida, parse_mode="HTML", reply_markup=main_menu())

@bot.message_handler(commands=['historial'])
def h_cmd(message):
    gestionar_historial(message.chat.id, message.from_user.id)

# --- CALLBACKS ---
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
        bot.send_message(call.message.chat.id, "<b>🔓 Acceso Gratis</b>\n\nCompleta el acortador para entrar:", parse_mode="HTML", reply_markup=markup)

    elif call.data.startswith("buy_p"):
        bot.answer_callback_query(call.id)
        p_info = {
            "buy_p1": ("Básico", 1),
            "buy_p3": ("Estándar", 3),
            "buy_p8": ("VIP", 8)
        }[call.data]
        bot.send_invoice(call.message.chat.id, title=f"Plan {p_info[0]}", description=f"Acceso VIP {p_info[0]}", invoice_payload=call.data, provider_token="", currency="XTR", prices=[types.LabeledPrice(label=p_info[0], amount=p_info[1])])

    elif call.data == "ver_help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"<b>📺 TUTORIAL:</b>\n\n{CANAL_TUTORIAL}", parse_mode="HTML")

# --- PROCESAMIENTO DE PAGOS ---
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payload = message.successful_payment.invoice_payload
    uid = message.from_user.id
    if payload == "buy_p1": entregar_acceso(message.chat.id, uid, 1, 1, "Plan Básico")
    elif payload == "buy_p3": entregar_acceso(message.chat.id, uid, 3, 4, "Plan Estándar")
    elif payload == "buy_p8": entregar_acceso(message.chat.id, uid, 15, 10, "Plan VIP")

if __name__ == "__main__":
    threading.Thread(target=run_mock_server, daemon=True).start()
    print("🚀 Bot iniciado con MongoDB Atlas...")
    bot.infinity_polling()

