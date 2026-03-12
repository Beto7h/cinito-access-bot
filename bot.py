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
db_temporal = {} # Memoria para links: {user_id: {'link': url, 'expira': timestamp}}

# --- SERVIDOR SEÑUELO (PUERTO 8060) ---
class MockServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Servidor Cinito Activo en Puerto 8060")

def run_mock_server():
    server = HTTPServer(('0.0.0.0', 8060), MockServer)
    server.serve_forever()

# --- LIMPIEZA AUTOMÁTICA (Cada 24h) ---
def limpiar_db():
    while True:
        ahora = time.time()
        te_fuiste = [uid for uid, data in db_temporal.items() if ahora > data['expira']]
        for uid in te_fuiste:
            del db_temporal[uid]
        time.sleep(3600)

# --- COMANDOS ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    params = message.text.split()

    if len(params) > 1 and params[1] == 'verificado':
        if user_id in db_temporal:
            bot.send_message(message.chat.id, "⚠️ Ya tienes un link activo. Revísalo en '📂 Enlaces Generados'.")
        else:
            try:
                invite = bot.create_chat_invite_link(GRUPO_ID, member_limit=1, expire_date=int(time.time()) + 86400)
                db_temporal[user_id] = {'link': invite.invite_link, 'expira': time.time() + 86400}
                bot.send_message(message.chat.id, "✅ ¡Acceso verificado! Tu enlace ha sido guardado en el historial.")
            except:
                bot.send_message(message.chat.id, "❌ Error: Hazme administrador del grupo primero.")
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(types.KeyboardButton("🔓 Generar Nuevo Enlace"))
        markup.row(types.KeyboardButton("📂 Enlaces Generados"))
        
        texto_bienvenida = (
            f"<b>🎬 Bienvenido a este bot oficial de Cinito</b>\n\n"
            f"Hola {message.from_user.first_name}, este bot te dará un link para unirte al canal o grupo seleccionado.\n\n"
            f"Usa los botones de abajo para gestionar tus accesos."
        )
        bot.send_message(message.chat.id, texto_bienvenida, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🔓 Generar Nuevo Enlace")
def generar_btn(message):
    url_acortada = f"https://gplinks.in/st?api={API_KEY_GPLINKS}&url=https://t.me/{BOT_USERNAME}?start=verificado"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Ir al Acortador", url=url_acortada))
    bot.send_message(message.chat.id, "Completa el acortador para recibir tu link de 24 horas:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📂 Enlaces Generados")
def historial_btn(message):
    user_id = message.from_user.id
    if user_id in db_temporal and time.time() < db_temporal[user_id]['expira']:
        bot.send_message(message.chat.id, f"<b>📂 Enlace Activo:</b>\n\n<code>{db_temporal[user_id]['link']}</code>\n\n<i>Válido por 24h. Si ya lo usaste, no funcionará de nuevo.</i>", parse_mode="HTML")
    else:
        if user_id in db_temporal: del db_temporal[user_id]
        bot.send_message(message.chat.id, "❌ No tienes links activos. Presiona /start para generar uno nuevo.")

if __name__ == "__main__":
    threading.Thread(target=run_mock_server, daemon=True).start()
    threading.Thread(target=limpiar_db, daemon=True).start()
    bot.infinity_polling()
          
