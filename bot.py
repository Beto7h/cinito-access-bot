import os
import time
import telebot
import threading
from telebot import types
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURACIÓN DE VARIABLES ---
TOKEN = os.getenv('BOT_TOKEN')
API_KEY_GPLINKS = os.getenv('GPLINKS_API')
GRUPO_ID = int(os.getenv('GRUPO_ID'))
BOT_USERNAME = os.getenv('BOT_USERNAME')
CANAL_TUTORIAL = os.getenv('CANAL_TUTORIAL', 'https://t.me/')

# ⚠️ TU ID PARA EL COMANDO /ventas:
ADMIN_ID = 7523334989 

bot = telebot.TeleBot(TOKEN)
db_temporal = {} # {user_id: {'link': url, 'expira': timestamp, 'tipo': 'free'/'vip'}}
stats = {"estrellas_ganadas": 0, "ventas_totales": 0}

# --- SERVIDOR PARA KOYEB ---
class MockServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Servidor Cinito Online - Activo")

def run_mock_server():
    server = HTTPServer(('0.0.0.0', 8060), MockServer)
    server.serve_forever()

def limpiar_db():
    while True:
        ahora = time.time()
        te_fuiste = [uid for uid, data in db_temporal.items() if ahora > data['expira']]
        for uid in te_fuiste: del db_temporal[uid]
        time.sleep(3600)

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

# --- LÓGICA DE HISTORIAL ---
def gestionar_historial(chat_id, user_id):
    ahora = time.time()
    if user_id in db_temporal:
        try:
            data = db_temporal[user_id]
            info = bot.get_chat_invite_link(GRUPO_ID, data['link'])
            cupos_usados = info.member_count
            cupos_totales = info.member_limit if info.member_limit else 1
            
            if ahora > data['expira']:
                del db_temporal[user_id]
                bot.send_message(chat_id, "❌ <b>Tu último enlace ha caducado por tiempo.</b>", parse_mode="HTML")
            elif cupos_usados >= cupos_totales:
                texto = f"<b>🚫 ENLACE AGOTADO</b>\n\nEl enlace <code>{data['link']}</code> ya no tiene cupos."
                if data.get('tipo') == 'free':
                    texto += "\n\n<i>💡 Tip: Con los Planes VIP entras sin anuncios y duran más tiempo.</i>"
                bot.send_message(chat_id, texto, parse_mode="HTML")
            else:
                restante = data['expira'] - ahora
                horas = int(restante / 3600)
                bot.send_message(chat_id, f"<b>📂 TU ENLACE ACTUAL:</b>\n\n👉 {data['link']}\n\n👥 Cupos: {cupos_totales - cupos_usados} de {cupos_totales}\n🕒 Vence en: {horas}h", parse_mode="HTML", disable_web_page_preview=True)
        except:
            bot.send_message(chat_id, "❌ No tienes enlaces activos.")
    else:
        bot.send_message(chat_id, "🧐 No tienes enlaces recientes.")

# --- COMANDOS ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    params = message.text.split()

    if len(params) > 1 and params[1] == 'verificado':
        entregar_acceso(message.chat.id, user_id, 1, 1, "Acceso Gratuito", "free")
    else:
        # MENSAJE DE BIENVENIDA RESTAURADO
        texto_bienvenida = (
            f"<b>🎬 ¡BIENVENIDO A CINITO VIP!</b>\n\n"
            f"Hola <b>{message.from_user.first_name}</b>, elige cómo obtener tu acceso:\n\n"
            f"----------------------------------\n"
            f"<b>🆓 OPCIÓN GRATUITA</b>\n"
            f"Completa el acortador para recibir tu link.\n"
            f"• <b>Vigencia del link:</b> 24 horas.\n"
            f"• <b>Límite:</b> 1 persona.\n"
            f"👉 <i>Usa el botón 'Acceso Gratis'.</i>\n\n"
            f"----------------------------------\n"
            f"<b>⭐ PASES RÁPIDOS (VIP)</b>\n"
            f"Entra al instante sin anuncios usando <b>Telegram Stars</b>:\n\n"
            f"🔹 <b>Plan Básico (1⭐):</b> 24h / 1 persona.\n"
            f"🔹 <b>Plan Estándar (3⭐):</b> 3 días / 4 personas.\n"
            f"🔹 <b>Plan VIP (8⭐):</b> 15 días / 10 personas.\n\n"
            f"⚠️ <i>Nota: Los enlaces caducan automáticamente al cumplir su tiempo o límite de personas.</i>\n\n"
            f"<b>¿Qué prefieres hacer hoy?</b> 👇"
        )
        bot.send_message(message.chat.id, texto_bienvenida, parse_mode="HTML", reply_markup=main_menu())

@bot.message_handler(commands=['historial'])
def cmd_historial(message):
    gestionar_historial(message.chat.id, message.from_user.id)

@bot.message_handler(commands=['ventas'])
def ver_ventas(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, f"<b>📊 REPORTE</b>\n\n⭐ Estrellas: {stats['estrellas_ganadas']}\n🛒 Ventas: {stats['ventas_totales']}", parse_mode="HTML")

# --- FUNCIÓN DE ENTREGA ---
def entregar_acceso(chat_id, user_id, dias, usos, nombre_plan, tipo="vip"):
    try:
        segundos = dias * 86400
        invite = bot.create_chat_invite_link(GRUPO_ID, member_limit=usos, expire_date=int(time.time()) + segundos)
        db_temporal[user_id] = {'link': invite.invite_link, 'expira': time.time() + segundos, 'tipo': tipo}
        
        texto = (
            f"<b>✅ ¡{nombre_plan} Activado!</b>\n\n"
            f"Tu enlace de unión es:\n👉 {invite.invite_link}\n\n"
            f"<i>Este link se guardó en tu historial por {dias} día(s). Si alcanzas el límite de {usos} persona(s), deberás generar uno nuevo.</i>"
        )
        bot.send_message(chat_id, texto, parse_mode="HTML", disable_web_page_preview=True)
    except:
        bot.send_message(chat_id, "❌ Error: Revisa los permisos del bot en el grupo.")

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    uid = call.from_user.id
    ahora = time.time()

    if call.data == "intentar_generar":
        if uid in db_temporal:
            try:
                info = bot.get_chat_invite_link(GRUPO_ID, db_temporal[uid]['link'])
                if info.member_count < 1 and ahora < db_temporal[uid]['expira']:
                    bot.answer_callback_query(call.id, "⚠️ Ya tienes un link activo.")
                    return bot.send_message(call.message.chat.id, f"<b>⚠️ YA TIENES UN LINK</b>\n\n👉 {db_temporal[uid]['link']}", parse_mode="HTML", disable_web_page_preview=True)
            except: pass
        
        bot.answer_callback_query(call.id)
        url = f"https://gplinks.in/st?api={API_KEY_GPLINKS}&url=https://t.me/{BOT_USERNAME}?start=verificado"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🚀 Ir al Acortador", url=url))
        bot.send_message(call.message.chat.id, "<b>🔓 Acceso Gratis</b>\n\nCompleta el acortador para entrar:", parse_mode="HTML", reply_markup=markup)

    elif call.data.startswith("buy_p"):
        bot.answer_callback_query(call.id)
        p = {"buy_p1": (1, "Básico"), "buy_p3": (3, "Estándar"), "buy_p8": (8, "VIP")}[call.data]
        bot.send_invoice(call.message.chat.id, title=f"Plan {p[1]}", description=f"Acceso VIP {p[1]}", invoice_payload=f"pay_{call.data}", provider_token="", currency="XTR", prices=[types.LabeledPrice(label=p[1], amount=p[0])])

    elif call.data == "ver_historial":
        bot.answer_callback_query(call.id)
        gestionar_historial(call.message.chat.id, uid)

    elif call.data == "ver_help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"<b>📺 TUTORIAL:</b>\n\n{CANAL_TUTORIAL}", parse_mode="HTML")

# --- PAGOS ---
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payload = message.successful_payment.invoice_payload
    uid = message.from_user.id
    if "p1" in payload: stats["estrellas_ganadas"] += 1; entregar_acceso(message.chat.id, uid, 1, 1, "Plan Básico")
    elif "p3" in payload: stats["estrellas_ganadas"] += 3; entregar_acceso(message.chat.id, uid, 3, 4, "Plan Estándar")
    elif "p8" in payload: stats["estrellas_ganadas"] += 8; entregar_acceso(message.chat.id, uid, 15, 10, "Plan VIP")
    stats["ventas_totales"] += 1

if __name__ == "__main__":
    threading.Thread(target=run_mock_server, daemon=True).start()
    threading.Thread(target=limpiar_db, daemon=True).start()
    bot.infinity_polling()
