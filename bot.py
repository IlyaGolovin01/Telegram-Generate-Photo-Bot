import os
import telebot
import urllib3
from dotenv import load_dotenv
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

from ai_logic import generate_image, get_remaining_images
from database import get_or_create_user, is_admin, log_request, get_logs, get_user_stats, set_admin, get_all_admins

bot = telebot.TeleBot(os.environ.get("TG_BOT_TOKEN"), threaded=False)

ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]


def main_menu(user_id):
    remaining = get_remaining_images()
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    
    if is_admin(user_id):
        keyboard.add(KeyboardButton(f"🎨 Сгенерировать (осталось: {remaining})"))
        keyboard.add(KeyboardButton("📁 Мои изображения"))
    keyboard.add(KeyboardButton("❓ Помощь"))
    if is_admin(user_id):
        keyboard.add(KeyboardButton("📊 Статистика"))
    return keyboard


@bot.message_handler(commands=["start"])
def cmd_start(message):
    user = get_or_create_user(message.chat.id, message.from_user.username, message.from_user.first_name)
    
    if message.chat.id in ADMIN_IDS and not is_admin(message.chat.id):
        set_admin(message.chat.id, 1)
    
    if is_admin(message.chat.id):
        welcome_text = "Привет! Я бот для генерации изображений.\n\nНажми кнопку ниже или используй команду /generate <запрос>"
    else:
        welcome_text = "Привет! Этот бот доступен только админам.\n\nСвяжись с администратором для получения доступа."
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(message.chat.id))


@bot.message_handler(commands=["generate"])
def cmd_generate(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "⛔ Доступ только для админов!")
        return
    
    user = get_or_create_user(message.chat.id, message.from_user.username, message.from_user.first_name)
    
    try:
        prompt = message.text.replace("/generate", "").strip()
        if not prompt:
            bot.reply_to(message, "Напиши запрос после команды /generate\nПример: /generate яблоко")
            return
    except Exception:
        bot.reply_to(message, "Используй: /generate <запрос>")
        return

    remaining = get_remaining_images()
    if remaining <= 0:
        log_request(user["id"], prompt, "error", "Лимит исчерпан")
        bot.reply_to(message, "⛔ Лимит исчерпан! Все токены использованы.")
        return

    try:
        safe_name = "".join(c for c in prompt if c.isalnum() or c in " -_").strip()[:50]
        if not safe_name:
            safe_name = "image"

        os.makedirs("images_tg", exist_ok=True)
        save_path = f"images_tg/{safe_name}.png"

        status_msg = bot.reply_to(message, f"🎨 Генерирую: {prompt}...\nОсталось: {remaining}")

        print(f"Generating image: {prompt}")
        generate_image(prompt, save_path)
        print(f"Saved to: {save_path}")

        with open(save_path, "rb") as photo:
            msg = bot.send_photo(message.chat.id, photo, reply_to_message_id=status_msg.message_id)

        bot.edit_message_text(f"✅ Готово! Осталось: {get_remaining_images()}", message.chat.id, status_msg.message_id)
        print(f"Sent: {msg.message_id}")
        
        log_request(user["id"], prompt, "success")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        log_request(user["id"], prompt, "error", str(e))
        bot.reply_to(message, f"Ошибка: {e}")


@bot.message_handler(func=lambda m: "Сгенерировать" in m.text)
def btn_generate(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "⛔ Доступ только для админов!")
        return
    
    remaining = get_remaining_images()
    if remaining <= 0:
        bot.reply_to(message, "⛔ Лимит исчерпан! Все токены использованы.")
    else:
        bot.reply_to(message, f"Напиши запрос для генерации картинки.\nОсталось генераций: {remaining}\n\nНапример: /generate кошка")


@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
def btn_stats(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "⛔ Доступ только для админов!")
        return
    
    stats = get_user_stats()
    logs = get_logs(20)
    
    text = "📊 *Статистика админов*\n\n"
    for s in stats:
        username = s["username"] or s["first_name"] or "Unknown"
        text += f"• {username}: {s['successful']}/{s['total_requests']} успешных\n"
    
    text += "\n📜 *Последние 20 запросов:*\n\n"
    for l in logs:
        status_icon = "✅" if l["status"] == "success" else "❌"
        text += f"{status_icon} {l['prompt'][:30]}... - {l['created_at']}\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(commands=["logs"])
def cmd_logs(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "⛔ Доступ только для админов!")
        return
    
    logs = get_logs(50)
    text = "📜 *Последние 50 запросов:*\n\n"
    for l in logs:
        status_icon = "✅" if l["status"] == "success" else "❌"
        username = l["username"] or l["first_name"] or "Unknown"
        text += f"{status_icon} {username}: {l['prompt'][:25]}... [{l['status']}]\n"
        text += f"   📅 {l['created_at']}\n"
        if l["error_message"]:
            text += f"   ❗ {l['error_message'][:50]}\n"
        text += "\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "📁 Мои изображения")
def btn_images(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "⛔ Доступ только для админов!")
        return
    
    if os.path.exists("images_tg"):
        files = sorted([f for f in os.listdir("images_tg") if f.endswith(".png")])
        if files:
            keyboard = InlineKeyboardMarkup()
            for f in files[:20]:
                keyboard.add(InlineKeyboardButton(f"📷 {f}", callback_data=f"view:{f}"))
            if len(files) > 20:
                keyboard.add(InlineKeyboardButton(f"Показать ещё ({len(files)-20})", callback_data="view_more"))
            bot.reply_to(message, f"Выбери изображение ({len(files)} шт.):", reply_markup=keyboard)
        else:
            bot.reply_to(message, "Пока нет сохранённых изображений.")
    else:
        bot.reply_to(message, "Пока нет сохранённых изображений.")


@bot.callback_query_handler(lambda c: c.data and c.data.startswith("view:"))
def callback_view_image(call):
    filename = call.data.replace("view:", "")
    filepath = f"images_tg/{filename}"
    if os.path.exists(filepath):
        with open(filepath, "rb") as photo:
            bot.send_photo(call.message.chat.id, photo, caption=f"📷 {filename}")
    else:
        bot.answer_callback_query(call.id, "Файл не найден")


@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def btn_help(message):
    help_text = "📖 *Инструкция*\n\n"
    help_text += "1. Нажми '🎨 Сгенерировать'\n"
    help_text += "2. Напиши запрос: /generate <что нужно>\n\n"
    help_text += "Примеры:\n"
    help_text += "• /generate кошка\n"
    help_text += "• /generate закат на море\n"
    help_text += "• /generate аниме персонаж\n\n"
    help_text += "Все изображения сохраняются в папку images_tg"
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")


bot.infinity_polling()