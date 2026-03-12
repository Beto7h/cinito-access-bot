import os
import time
import telebot
import threading
from telebot import types
from pymongo import MongoClient
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURACIÓN DE VARIABLES ---
TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
API_KEY_GPLINKS = os.getenv('GPLINKS_API')
GRUPO_ID = int(os.getenv('GRUPO_ID'))
BOT_USERNAME = os.getenv('BOT_USERNAME')
CANAL_TUTORIAL = os.getenv('CANAL_TUTORIAL', 'https://t.me/')
ADMIN_ID = 7523334989 

bot = telebot.TeleBot(TOKEN)

# --- CONEXIÓN A MONGODB ATLAS ---
client = MongoClient(MONGO_URI)
db = client['cinito_bot']
links_col = db['links']
stats_col = db['stats']

# --- SERVIDOR PARA KOYEB ---
class MockServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Servidor Cinito Online - Activo")

def run_mock_server():
    server = HTTPServer(('0.0.0.0', 8060), MockServer)
    server.serve_forever()

# --- MENÚS ---
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

# --- FUNCIÓN DE ENTREGA (CON PERSISTENCIA) ---
def entregar_acceso(chat_id, user_id, dias, usos, nombre_plan, tipo="vip"):
    try:
        segundos = dias * 86400
        invite = bot.create_chat_invite_link(GRUPO_ID, member_limit=usos, expire_date=int(time.time()) + segundos)
        
        # 💾 Guardado eterno en MongoDB
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

        # 📈 Registro de Tráfico
        stats_col.update_one(
            {"_id": "global_stats"},
            {"$inc": {"accesos_totales": 1, f"accesos_{tipo}": 1}},
            upsert=True
        )
        
        texto = (
            f"<b>✅ ¡{nombre_plan} Activado!</b>\n\n"
            f"Tu enlace de unión es:\n👉 {invite.invite_link}\n\n"
            f"<i>Este link se guardó en tu historial por {dias} día(s).</i>"
        )
        bot.send_message(chat_id, texto, parse_mode="HTML", disable_web_page_preview=True)
        
        # Aviso al Admin
        bot.send_message(ADMIN_ID, f"📢 <b>NUEVO ACCESO</b>\n👤 ID: <code>{user_id}</code>\n🎫 Plan: {nombre_plan}", parse_mode="HTML")
    except Exception as e:
        bot.send_message(chat_id, "❌ Error: Revisa los permisos del bot en el grupo.")

# --- LÓGICA DE HISTORIAL ---
def gestionar_historial(chat_id, user_id):
    ahora = time.time()
    data = links_col.find_one({"user_id": user_id})

    if data:
        if ahora < data['expira']:
            bot.send_message(chat_id, f"<b>📂 TU ENLACE ACTUAL:</b>\n\n👉 {data['link']}\n\n<i>Válido por el tiempo restante de tu plan.</i>", parse_mode="HTML", disable_web_page_preview=True)
        else:
            links_col.delete_one({"user_id": user_id})
            bot.send_message(chat_id, "❌ Tu enlace ha expirado.")
    else:
        bot.send_message(chat_id, "🧐 No tienes enlaces activos.")

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
            f"🔹 <b>Plan VIP (8⭐):</b> 15 días / 10 usos\n\n"
            f"<b>¿Qué prefieres hacer hoy?</b> 👇"
        )
        bot.send_message(message.chat.id, texto_bienvenida, parse_mode="HTML", reply_markup=main_menu())

@bot.message_handler(commands=['ventas'])
def ver_ventas(message):
    if message.from_user.id == ADMIN_ID:
        data = stats_col.find_one({"_id": "global_stats"})
        if data:
            texto = (
                f"<b>📊 REPORTE CINITO VIP</b>\n\n"
                f"💰 <b>Estrellas:</b> {data.get('estrellas_totales', 0)} ⭐\n"
                f"🛒 <b>Ventas VIP:</b> {data.get('ventas_totales', 0)}\n"
                f"🆓 <b>Entradas Gratis:</b> {data.get('accesos_free', 0)}\n"
                f"👥 <b>Total Accesos:</b> {data.get('accesos_totales', 0)}"
            )
        else:
            texto = "<b>📊 REPORTE</b>\n\nNo hay datos registrados."
        bot.send_message(message.chat.id, texto, parse_mode="HTML")

@bot.message_handler(commands=['reset'])
def reset_stats(message):
    if message.from_user.id == ADMIN_ID:
        params = message.text.split()
        if len(params) > 1 and params[1].lower() == "confirmar":
            stats_col.update_one({"_id": "global_stats"}, {"$set": {"estrellas_totales": 0, "ventas_totales": 0, "accesos_totales": 0, "accesos_free": 0, "accesos_vip": 0}}, upsert=True)
            bot.send_message(message.chat.id, "✅ Estadísticas reiniciadas.")
        else:
            bot.send_message(message.chat.id, "⚠️ Para resetear usa: <code>/reset confirmar</code>", parse_mode="HTML")

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    uid = call.from_user.id
    if call.data == "ver_historial":
        bot.answer_callback_query(call.id); gestionar_historial(call.message.chat.id, uid)
    elif call.data == "intentar_generar":
        bot.answer_callback_query(call.id)
        url = f"https://gplinks.in/st?api={API_KEY_GPLINKS}&url=https://t.me/{BOT_USERNAME}?start=verificado"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🚀 Ir al Acortador", url=url))
        bot.send_message(call.message.chat.id, "<b>🔓 Acceso Gratis</b>\nCompleta el acortador:", parse_mode="HTML", reply_markup=markup)
    elif call.data.startswith("buy_p"):
        bot.answer_callback_query(call.id)
        p = {"buy_p1": (1, "Básico"), "buy_p3": (3, "Estándar"), "buy_p8": (8, "VIP")}[call.data]
        bot.send_invoice(call.message.chat.id, title=f"Plan {p[1]}", description=f"Acceso VIP {p[1]}", invoice_payload=call.data, provider_token="", currency="XTR", prices=[types.LabeledPrice(label=p[1], amount=p[0])])
    elif call.data == "ver_help":
        bot.answer_callback_query(call.id); bot.send_message(call.message.chat.id, f"<b>📺 TUTORIAL:</b>\n\n{CANAL_TUTORIAL}", parse_mode="HTML")

# --- PAGOS ---
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payload = message.successful_payment.invoice_payload
    monto = message.successful_payment.total_amount
    uid = message.from_user.id
    
    stats_col.update_one({"_id": "global_stats"}, {"$inc": {"estrellas_totales": monto, "ventas_totales": 1}}, upsert=True)
    
    if "p1" in payload: entregar_acceso(message.chat.id, uid, 1, 1, "Plan Básico", "vip")
    elif "p3" in payload: entregar_acceso(message.chat.id, uid, 3, 4, "Plan Estándar", "vip")
    elif "p8" in payload: entregar_acceso(message.chat.id, uid, 15, 10, "Plan VIP", "vip")

if __name__ == "__main__":
    threading.Thread(target=run_mock_server, daemon=True).start()
    bot.infinity_polling()
