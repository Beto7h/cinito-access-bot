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

bot = telebot.TeleBot(TOKEN)
db_temporal = {} # {user_id: {'link': url, 'expira': timestamp}}

# --- SERVIDOR PARA KOYEB (Puerto 8060) ---
class MockServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Servidor de Cinito funcionando correctamente.")

def run_mock_server():
    server = HTTPServer(('0.0.0.0', 8060), MockServer)
    server.serve_forever()

# --- LIMPIEZA AUTOMÁTICA DE MEMORIA ---
def limpiar_db():
    while True:
        ahora = time.time()
        te_fuiste = [uid for uid, data in db_temporal.items() if ahora > data['expira']]
        for uid in te_fuiste:
            del db_temporal[uid]
        time.sleep(3600) # Revisa cada hora

# --- MENÚ INLINE PRINCIPAL ---
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

    # Caso: El usuario regresa del acortador
    if len(params) > 1 and params[1] == 'verificado':
        if user_id not in db_temporal:
            try:
                invite = bot.create_chat_invite_link(GRUPO_ID, member_limit=1, expire_date=int(time.time()) + 86400)
                db_temporal[user_id] = {'link': invite.invite_link, 'expira': time.time() + 86400}
            except Exception as e:
                return bot.send_message(message.chat.id, "❌ Error: El bot debe ser admin del grupo con permiso de invitaciones.")

        data = db_temporal[user_id]
        texto = (
            f"<b>✅ ¡Acceso verificado!</b>\n\n"
            f"Tu enlace de unión es el siguiente:\n"
            f"👉 <code>{data['link']}</code>\n\n"
            f"<i>Este link se guardó en tu historial por 24h. Si lo usas y sales del grupo, deberás generar uno nuevo.</i>"
        )
        bot.send_message(message.chat.id, texto, parse_mode="HTML", reply_markup=main_menu())
    
    # Caso: Bienvenida normal
    else:
        texto_bienvenida = (
            f"<b>🎬 ¡Bienvenido a este bot oficial de Cinito!</b>\n\n"
            f"Hola {message.from_user.first_name}, selecciona una opción para gestionar tu acceso al grupo VIP."
        )
        bot.send_message(message.chat.id, texto_bienvenida, parse_mode="HTML", reply_markup=main_menu())

@bot.message_handler(commands=['id'])
def get_id(message):
    bot.reply_to(message, f"🆔 Tu ID de usuario es: <code>{message.from_user.id}</code>", parse_mode="HTML")

# --- MANEJO DE BOTONES (CALLBACKS) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    ahora = time.time()
    
    if call.data == "intentar_generar":
        # Verificar si ya existe un link y si sigue siendo válido
        if user_id in db_temporal:
            data = db_temporal[user_id]
            try:
                invite_info = bot.get_chat_invite_link(GRUPO_ID, data['link'])
                
                # Si el link ya se usó (member_count >= 1), permitimos generar otro
                if invite_info.member_count >= 1 or ahora > data['expira']:
                    del db_temporal[user_id]
                else:
                    # Si el link sigue vivo y sin usar, bloqueamos el acortador
                    bot.answer_callback_query(call.id, "⚠️ Ya tienes un link activo.")
                    texto_bloqueo = (
                        f"<b>🎬 AVISO DE CINITO</b>\n\n"
                        f"Ya tienes un enlace generado que <b>aún no has utilizado</b>.\n\n"
                        f"No es necesario pasar el acortador de nuevo. Usa tu enlace actual:\n\n"
                        f"👉 <code>{data['link']}</code>"
                    )
                    return bot.send_message(call.message.chat.id, texto_bloqueo, parse_mode="HTML")
            except:
                # Si hay error (link borrado, etc), permitimos uno nuevo
                del db_temporal[user_id]

        # Si llegamos aquí, mandamos al acortador
        bot.answer_callback_query(call.id)
        url_acortada = f"https://gplinks.in/st?api={API_KEY_GPLINKS}&url=https://t.me/{BOT_USERNAME}?start=verificado"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Ir al Acortador", url=url_acortada))
        bot.send_message(call.message.chat.id, "<b>🔓 ¡Acceso Disponible!</b>\n\nCompleta el acortador para obtener tu enlace de entrada:", parse_mode="HTML", reply_markup=markup)

    elif call.data == "ver_historial":
        if user_id in db_temporal and ahora < db_temporal[user_id]['expira']:
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id, 
                f"<b>📂 HISTORIAL DE ENLACES:</b>\n\n"
                f"🔗 Link: <code>{db_temporal[user_id]['link']}</code>\n\n"
                f"<i>Recuerda: si el link ya fue usado, no funcionará otra vez.</i>",
                parse_mode="HTML"
            )
        else:
            bot.answer_callback_query(call.id, "❌ No tienes enlaces activos.", show_alert=True)

    elif call.data == "ver_help":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id, 
            f"<b>📺 TUTORIAL:</b>\n\nSi no sabes cómo saltar el acortador, mira este video:\n{CANAL_TUTORIAL}",
            parse_mode="HTML"
        )

# --- INICIO DEL BOT ---
if __name__ == "__main__":
    print("Iniciando servidor y bot...")
    threading.Thread(target=run_mock_server, daemon=True).start()
    threading.Thread(target=limpiar_db, daemon=True).start()
    bot.infinity_polling()
