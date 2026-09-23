import os

from unixgram import Bot, InlineKeyboardMarkup, InlineKeyboardButton

from db import (
    init_db,
    get_or_create_user,
    get_balance,
    change_balance,
    find_item,
    record_purchase,
    count_item,
    create_reg_token,
    SHOP_ITEMS,
)

TOKEN = os.environ.get("UNIXGRAM_TOKEN", "")
SITE_URL = os.environ.get("SITE_URL", "https://example.com")

bot = Bot(TOKEN)


@bot.message_handler(commands=["start"])
def cmd_start(message):
    get_or_create_user(message.from_user.id, message.from_user.username)
    bot.send_message(
        message.chat.id,
        "/balance — баланс\n"
        "/shop — магазин\n"
        "/inventory — покупки\n"
        "/link — привязать сайт",
    )


@bot.message_handler(commands=["balance"])
def cmd_balance(message):
    get_or_create_user(message.from_user.id, message.from_user.username)
    balance = get_balance(message.from_user.id)
    bot.send_message(message.chat.id, f"Баланс: {balance}")


@bot.message_handler(commands=["shop"])
def cmd_shop(message):
    get_or_create_user(message.from_user.id, message.from_user.username)
    kb = InlineKeyboardMarkup()
    for item in SHOP_ITEMS:
        kb.row(InlineKeyboardButton(f"{item['name']} — {item['price']}", callback_data=f"buy:{item['id']}"))
    bot.send_message(message.chat.id, "Магазин:", reply_markup=kb)


@bot.callback_query_handler(func=lambda q: q.data.startswith("buy:"))
def on_buy(query):
    item_id = query.data.split(":", 1)[1]
    item = find_item(item_id)
    if item is None:
        bot.answer_callback_query(query.id, "Такого товара нет")
        return

    user_id = query.from_user.id
    get_or_create_user(user_id, query.from_user.username)
    balance = get_balance(user_id)

    if balance < item["price"]:
        bot.answer_callback_query(query.id, "Не хватает баланса", show_alert=True)
        return

    change_balance(user_id, -item["price"])
    record_purchase(user_id, item_id)
    bot.answer_callback_query(query.id, f"Куплено: {item['name']}")
    bot.send_message(query.message.chat.id, f"{item['name']} куплен. Остаток: {get_balance(user_id)}")


@bot.message_handler(commands=["inventory"])
def cmd_inventory(message):
    get_or_create_user(message.from_user.id, message.from_user.username)
    lines = []
    for item in SHOP_ITEMS:
        n = count_item(message.from_user.id, item["id"])
        if n:
            lines.append(f"{item['name']} x{n}")
    bot.send_message(message.chat.id, "\n".join(lines) if lines else "Пусто")


@bot.message_handler(commands=["link"])
def cmd_link(message):
    get_or_create_user(message.from_user.id, message.from_user.username)
    token, _ = create_reg_token(message.from_user.id)
    url = f"{SITE_URL}/register?token={token}"
    text = f"{url}\nСсылка действует 1 минуту."
    try:
        # На случай, если сам мессенджер делает GET по ссылке для превью —
        # отключаем превью, чтобы это не расходовало токен раньше времени.
        bot.send_message(message.chat.id, text, disable_web_page_preview=True)
    except TypeError:
        bot.send_message(message.chat.id, text)


def run_polling():
    """Крутить long-poll бота. Если порвётся сеть — не падать, а пробовать снова."""
    init_db()
    while True:
        try:
            bot.polling()
        except Exception as e:
            print("[bot] обрыв поллинга:", e, flush=True)


if __name__ == "__main__":
    run_polling()
