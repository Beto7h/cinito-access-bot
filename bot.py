import os
import time
import telebot
import threading
from telebot import types
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURACIÓN ---
TOKEN = os.getenv('BOT_TOKEN')
API_KEY_GPLINKS = os.getenv('GPLINKS_API')
GRUPO_ID = int(os.getenv('GRUPO_ID'))
BOT_USERNAME = os.getenv('BOT_USERNAME')
CANAL_TUTORIAL = os.getenv('CANAL_TUTORIAL', 'https://t.me/')

bot = telebot.TeleBot(TOKEN)
db_temporal = {} 

# --- SERVIDOR PARA KOYEB ---
class MockServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Servidor de Cinito Online")

def run_mock_server():
    server = HTTPServer(('0.0.0.0', 8060), MockServer)
    server.serve_forever()

def limpiar_db():
    while True:
        ahora = time.time()
        te_fuiste = [uid for uid, data in db_temporal.items() if ahora > data['expira']]
        for uid in te_fuiste: del db_temporal[uid]
        time.sleep(3600)

# --- MENÚ ---
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_generar = types.InlineKeyboardButton("🔓 Generar Nuevo Enlace", callback_data="intentar_generar")
    btn_historial = types.InlineKeyboardButton("📂 Enlaces Generados", callback_data="ver_historial")
    btn_help = types.InlineKeyboardButton("❓ Ayuda / Tutorial", callback_data="ver_help")
    markup.add(btn_generar, btn_historial, btn_help)
    return markup

# --- COMANDOS ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    params = message.text.split()

    if len(params) > 1 and params[1] == 'verificado':
        if user_id not in db_temporal:
            try:
                invite = bot.create_chat_invite_link(GRUPO_ID, member_limit=1, expire_date=int(time.time()) + 86400)
                db_temporal[user_id] = {'link': invite.invite_link, 'expira': time.time() + 86400}
            except:
                return bot.send_message(message.chat.id, "❌ Error: Hazme admin del grupo.")

        data = db_temporal[user_id]
        texto = (
            f"<b>✅ ¡Acceso verificado!</b>\n\n"
            f"Tu enlace de unión es el siguiente:\n"
            f"👉 {data['link']}\n\n"
            f"<i>Este link se guardó en tu historial por 24h. Si sales del grupo, deberás generar uno nuevo.</i>"
        )
        bot.send_message(message.chat.id, texto, parse_mode="HTML", reply_markup=main_menu(), disable_web_page_preview=True)
    
    else:
        bot.send_message(message.chat.id, "<b>🎬 ¡Bienvenido a Cinito!</b>\n\nSelecciona una opción:", parse_mode="HTML", reply_markup=main_menu())

# --- MANEJO DE BOTONES (BLOQUEO ESTRICTO) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    ahora = time.time()
    
    if call.data == "intentar_generar":
        if user_id in db_temporal:
            data = db_temporal[user_id]
            try:
                invite_info = bot.get_chat_invite_link(GRUPO_ID, data['link'])
                
                # BLOQUEO SI EL LINK NO SE HA USADO
                if invite_info.member_count < 1 and ahora < data['expira']:
                    bot.answer_callback_query(call.id, "⚠️ Tienes un acceso pendiente.")
                    texto_bloqueo = (
                        f"<b>⚠️ ACCESO PENDIENTE</b>\n\n"
                        f"Tienes un enlace pendiente de usar y no puedes generar más links hasta que te unas al grupo.\n\n"
                        f"🔗 <b>Tu enlace actual:</b>\n👉 {data['link']}"
                    )
                    return bot.send_message(call.message.chat.id, texto_bloqueo, parse_mode="HTML", disable_web_page_preview=True)
                else:
                    # Si ya entró (member_count >= 1), borramos para permitir nuevo pago
                    del db_temporal[user_id]
            except:
                del db_temporal[user_id]

        # SI PASA EL FILTRO, MANDA AL ACORTADOR
        bot.answer_callback_query(call.id)
        url_acortada = f"https://gplinks.in/st?api={API_KEY_GPLINKS}&url=https://t.me/{BOT_USERNAME}?start=verificado"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Ir al Acortador", url=url_acortada))
        bot.send_message(call.message.chat.id, "<b>🔓 ¡Acceso Disponible!</b>\n\nCompleta el acortador para obtener tu enlace:", parse_mode="HTML", reply_markup=markup)

    elif call.data == "ver_historial":
        if user_id in db_temporal and ahora < db_temporal[user_id]['expira']:
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id, 
                f"<b>📂 HISTORIAL DE ENLACES:</b>\n\n🔗 Link: {db_temporal[user_id]['link']}",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            bot.answer_callback_query(call.id, "❌ No tienes enlaces activos.", show_alert=True)

    elif call.data == "ver_help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"<b>📺 TUTORIAL:</b>\n\n{CANAL_TUTORIAL}", parse_mode="HTML")

if __name__ == "__main__":
    threading.Thread(target=run_mock_server, daemon=True).start()
    threading.Thread(target=limpiar_db, daemon=True).start()
    bot.infinity_polling()
