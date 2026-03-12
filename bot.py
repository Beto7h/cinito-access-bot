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

# ⚠️ PON TU ID AQUÍ PARA USAR EL COMANDO /ventas:
ADMIN_ID = 7523334989 

bot = telebot.TeleBot(TOKEN)
db_temporal = {} 
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

# --- COMANDOS ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    params = message.text.split()

    if len(params) > 1 and params[1] == 'verificado':
        entregar_acceso(message.chat.id, user_id, 1, 1, "Acceso Gratuito")
    else:
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

@bot.message_handler(commands=['id'])
def get_id(message):
    bot.reply_to(message, f"🆔 Tu ID es: <code>{message.from_user.id}</code>", parse_mode="HTML")

@bot.message_handler(commands=['ventas'])
def ver_ventas(message):
    if message.from_user.id == ADMIN_ID:
        texto = (
            f"<b>📊 REPORTE DE VENTAS</b>\n\n"
            f"⭐ Estrellas totales: {stats['estrellas_ganadas']}\n"
            f"🛒 Ventas realizadas: {stats['ventas_totales']}"
        )
        bot.send_message(message.chat.id, texto, parse_mode="HTML")

# --- FUNCIÓN DE ENTREGA ---
def entregar_acceso(chat_id, user_id, dias, usos, nombre_plan):
    try:
        segundos_validez = dias * 86400
        invite = bot.create_chat_invite_link(
            GRUPO_ID, 
            member_limit=usos, 
            expire_date=int(time.time()) + segundos_validez
        )
        db_temporal[user_id] = {'link': invite.invite_link, 'expira': time.time() + segundos_validez}
        
        texto = (
            f"<b>✅ ¡{nombre_plan} Activado!</b>\n\n"
            f"Tu enlace de unión es:\n👉 {invite.invite_link}\n\n"
            f"🟢 <b>Capacidad:</b> {usos} persona(s)\n"
            f"🕒 <b>Expira en:</b> {dias} día(s)\n\n"
            f"⚠️ <i>Únete antes de que el tiempo se agote.</i>"
        )
        bot.send_message(chat_id, texto, parse_mode="HTML", disable_web_page_preview=True)
    except:
        bot.send_message(chat_id, "❌ Error al generar el acceso. Revisa mis permisos de admin.")

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    uid = call.from_user.id
    ahora = time.time()

    planes = {
        "buy_p1": {"stars": 1, "label": "Plan Básico", "desc": "24h - 1 persona"},
        "buy_p3": {"stars": 3, "label": "Plan Estándar", "desc": "3 días - 4 personas"},
        "buy_p8": {"stars": 8, "label": "Plan VIP", "desc": "15 días - 10 personas"}
    }

    if call.data in planes:
        if uid in db_temporal:
            try:
                info = bot.get_chat_invite_link(GRUPO_ID, db_temporal[uid]['link'])
                if info.member_count < 1:
                    bot.answer_callback_query(call.id, "⚠️ Tienes un link activo.")
                    return bot.send_message(call.message.chat.id, f"<b>⚠️ YA TIENES UN LINK</b>\n\nÚsalo antes de comprar otro:\n👉 {db_temporal[uid]['link']}", parse_mode="HTML", disable_web_page_preview=True)
            except: pass

        p = planes[call.data]
        bot.answer_callback_query(call.id)
        bot.send_invoice(call.message.chat.id, title=p['label'], description=p['desc'], invoice_payload=f"pay_{call.data}", provider_token="", currency="XTR", prices=[types.LabeledPrice(label=p['label'], amount=p['stars'])])

    elif call.data == "intentar_generar":
        if uid in db_temporal:
            try:
                info = bot.get_chat_invite_link(GRUPO_ID, db_temporal[uid]['link'])
                if info.member_count < 1:
                    bot.answer_callback_query(call.id, "⚠️ Acceso pendiente.")
                    return bot.send_message(call.message.chat.id, f"<b>⚠️ ACCESO PENDIENTE</b>\n\nTienes un enlace sin usar. No puedes generar más hasta que te unas.\n\n👉 {db_temporal[uid]['link']}", parse_mode="HTML", disable_web_page_preview=True)
            except: pass
        
        bot.answer_callback_query(call.id)
        url = f"https://gplinks.in/st?api={API_KEY_GPLINKS}&url=https://t.me/{BOT_USERNAME}?start=verificado"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🚀 Ir al Acortador", url=url))
        bot.send_message(call.message.chat.id, "<b>🔓 Acceso Gratis</b>\n\nCompleta el acortador (Válido 24h / 1 persona):", parse_mode="HTML", reply_markup=markup)

    elif call.data == "ver_historial":
        if uid in db_temporal and ahora < db_temporal[uid]['expira']:
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"<b>📂 TU ENLACE ACTUAL:</b>\n\n👉 {db_temporal[uid]['link']}", parse_mode="HTML", disable_web_page_preview=True)
        else:
            bot.answer_callback_query(call.id, "No tienes enlaces activos.", show_alert=True)

    elif call.data == "ver_help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"<b>📺 TUTORIAL:</b>\n\n{CANAL_TUTORIAL}", parse_mode="HTML")

# --- PROCESAMIENTO PAGO ---
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payload = message.successful_payment.invoice_payload
    uid = message.from_user.id
    if payload == "pay_buy_p1":
        stats["estrellas_ganadas"] += 1; stats["ventas_totales"] += 1
        entregar_acceso(message.chat.id, uid, 1, 1, "Plan Básico")
    elif payload == "pay_buy_p3":
        stats["estrellas_ganadas"] += 3; stats["ventas_totales"] += 1
        entregar_acceso(message.chat.id, uid, 3, 4, "Plan Estándar")
    elif payload == "pay_buy_p8":
        stats["estrellas_ganadas"] += 8; stats["ventas_totales"] += 1
        entregar_acceso(message.chat.id, uid, 15, 10, "Plan VIP")

if __name__ == "__main__":
    threading.Thread(target=run_mock_server, daemon=True).start()
    threading.Thread(target=limpiar_db, daemon=True).start()
    bot.infinity_polling()
