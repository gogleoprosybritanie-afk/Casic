import telebot
from telebot import types
from tinydb import TinyDB, Query
import time
from datetime import datetime
from config import TOKEN, CHANNEL_ID, CHANNEL_LINK, ADMIN_CHANNEL_ID
import sys

def create_bot():
    global BOT_USERNAME 
    try:
        bot = telebot.TeleBot(TOKEN)
        db = TinyDB('db.json')
        User = Query()
        bot_info = bot.get_me()
        BOT_USERNAME = bot_info.username

        @bot.message_handler(commands=['start'])
        def start_handler(message):
            try:
                user_id = message.from_user.id
                username = message.from_user.username or "NoUsername"
                first_name = message.from_user.first_name
                last_name = message.from_user.last_name or ""
                param = message.text.split()[1] if len(message.text.split()) > 1 else None

                if not db.get(User.user_id == user_id):
                    db.insert({
                        'user_id': user_id,
                        'balance': 0,
                        'bets_count': 0,
                        'total_earned': 0,
                        'reg_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'first_name': first_name,
                        'last_name': last_name
                    })

                if param == "bet":
                    user_data = db.get(User.user_id == user_id)
                    bot.send_message(message.chat.id,
                                   f"<b>Пришлите сумму звёзд для оплаты ставки.</b>\n\n"
                                   f"Баланс: <code>{user_data['balance']} звёзд</code>",
                                   parse_mode='HTML')
                    bot.register_next_step_handler(message, process_bet_amount)
                else:
                    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                    btn_profile = types.KeyboardButton("⚡️ Профиль")
                    btn_add_stars = types.KeyboardButton("💰 Пополнить звёзды")
                    btn_withdraw = types.KeyboardButton("🎁 Вывести звёзды")
                    markup.add(btn_profile, btn_add_stars)
                    markup.add(btn_withdraw)
                    
                    bot.send_message(message.chat.id,
                                   f"<b>👋 Добро пожаловать, @{username}</b>\n\n"
                                   f"Канал со ставками - <a href='{CHANNEL_LINK}'>тык</a>",
                                   parse_mode='HTML',
                                   reply_markup=markup)
            except Exception as e:
                bot.send_message(message.chat.id, "Произошла ошибка, попробуйте ещё раз")

        @bot.message_handler(func=lambda message: message.text == "🎁 Вывести звёзды")
        def withdraw_stars_handler(message):
            try:
                user_id = message.from_user.id
                user_data = db.get(User.user_id == user_id)
                balance = user_data['balance']
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                buttons = [
                    types.InlineKeyboardButton("15 звёзд", callback_data="withdraw_15"),
                    types.InlineKeyboardButton("25 звёзд", callback_data="withdraw_25"),
                    types.InlineKeyboardButton("50 звёзд", callback_data="withdraw_50"),
                    types.InlineKeyboardButton("100 звёзд", callback_data="withdraw_100"),
                    types.InlineKeyboardButton("150 звёзд", callback_data="withdraw_150"),
                    types.InlineKeyboardButton("350 звёзд", callback_data="withdraw_350"),
                    types.InlineKeyboardButton("500 звёзд", callback_data="withdraw_500")
                ]
                markup.add(*buttons)
                
                bot.send_message(message.chat.id,
                               f"<b>Баланс:</b> <code>{balance} звёзд</code>\n\n"
                               f"<b>Выбери сумму звёзд которые вы хотите вывести.</b>",
                               parse_mode='HTML',
                               reply_markup=markup)
            except Exception as e:
                bot.send_message(message.chat.id, "Произошла ошибка при выводе звёзд")

        @bot.callback_query_handler(func=lambda call: call.data.startswith("withdraw_"))
        def withdraw_amount_choice(call):
            try:
                user_id = call.from_user.id
                user_data = db.get(User.user_id == user_id)
                count = int(call.data.split("_")[1])
                
                if user_data['balance'] < count:
                    bot.answer_callback_query(call.id, "Недостаточно звёзд на балансе!")
                    return
                
                markup = types.InlineKeyboardMarkup()
                btn_yes = types.InlineKeyboardButton("Да", callback_data=f"confirm_withdraw_{count}")
                btn_no = types.InlineKeyboardButton("Отмена", callback_data="cancel_withdraw")
                markup.add(btn_yes, btn_no)
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"<b>Вы точно хотите вывести {count} звёзд?</b>",
                    parse_mode='HTML',
                    reply_markup=markup
                )
            except Exception as e:
                bot.answer_callback_query(call.id, "Произошла ошибка при выборе суммы")

        @bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_withdraw_"))
        def confirm_withdraw(call):
            try:
                user_id = call.from_user.id
                count = int(call.data.split("_")[2])
                user_data = db.get(User.user_id == user_id)
                username = call.from_user.username or "NoUsername"
                
                new_balance = user_data['balance'] - count
                db.update({'balance': new_balance}, User.user_id == user_id)
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="<b>Вы подали заявку на вывод звёзд.</b>\n\n"
                         "<b>В течение 72 часов заявка будет рассмотрена администратором и вам будет отправлен подарок, из которого вы получите звёзды.</b>",
                    parse_mode='HTML'
                )
                
                markup = types.InlineKeyboardMarkup()
                btn_issued = types.InlineKeyboardButton("Выдано", callback_data=f"issued_{user_id}_{count}")
                markup.add(btn_issued)
                
                admin_msg = bot.send_message(
                    ADMIN_CHANNEL_ID,
                    f"<b>Новая заявка</b>\n\n"
                    f"<blockquote><b>ID: {user_id}</b></blockquote>\n"
                    f"<blockquote><b>Юзернейм: @{username}</b></blockquote>\n"
                    f"<code>{count} звёзд</code>",
                    parse_mode='HTML',
                    reply_markup=markup
                )
            except Exception as e:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                                    text="Произошла ошибка при подтверждении вывода")

        @bot.callback_query_handler(func=lambda call: call.data == "cancel_withdraw")
        def cancel_withdraw(call):
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="Вывод звёзд отменён",
                    parse_mode='HTML'
                )
            except Exception as e:
                pass

        @bot.callback_query_handler(func=lambda call: call.data.startswith("issued_"))
        def issue_withdraw(call):
            try:
                user_id = int(call.data.split("_")[1])
                count = int(call.data.split("_")[2])
                username = call.from_user.username or "NoUsername"
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"<b>Новая заявка</b>\n\n"
                         f"<blockquote><b>ID: {user_id}</b></blockquote>\n"
                         f"<blockquote><b>Юзернейм: @{username}</b></blockquote>\n"
                         f"<code>{count} звёзд</code>\n\n"
                         f"<pre><b>Выдано</b></pre>",
                    parse_mode='HTML'
                )
                
                bot.send_message(
                    user_id,
                    f"<b>✅ Ваша заявка была выполнена, ищите сообщение с подарком за {count} звёзд от нашего администратора.</b>",
                    parse_mode='HTML'
                )
            except Exception as e:
                pass

        def process_bet_amount(message):
            try:
                user_id = message.from_user.id
                amount = int(message.text)
                user_data = db.get(User.user_id == user_id)
                if amount <= 0:
                    bot.send_message(message.chat.id, "<b>Сумма звёзд должна быть больше нуля</b>")
                    return
                if amount > user_data['balance']:
                    bot.send_message(message.chat.id, "Недостаточно звёзд на балансе!")
                    return
                    
                markup = types.InlineKeyboardMarkup()
                btn_more = types.InlineKeyboardButton("Больше", callback_data=f"game_more_{amount}")
                btn_less = types.InlineKeyboardButton("Меньше", callback_data=f"game_less_{amount}")
                markup.add(btn_more, btn_less)
                
                bot.send_message(message.chat.id,
                               "<b>Выберите игру в которую хотите сыграть</b>",
                               parse_mode='HTML',
                               reply_markup=markup)
            except ValueError:
                bot.send_message(message.chat.id, "Пожалуйста, введите число!")
            except Exception as e:
                bot.send_message(message.chat.id, "Произошла ошибка при обработке ставки")

        @bot.callback_query_handler(func=lambda call: call.data.startswith("game_"))
        def game_choice(call):
            try:
                user_id = call.from_user.id
                game_type, amount = call.data.split("_")[1], int(call.data.split("_")[2])
                
                markup = types.InlineKeyboardMarkup()
                btn_yes = types.InlineKeyboardButton("Да", callback_data=f"confirm_{game_type}_{amount}")
                btn_cancel = types.InlineKeyboardButton("Отмена", callback_data="cancel")
                markup.add(btn_yes, btn_cancel)
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="<b>Вы точно хотите сыграть в ставку?</b>",
                    parse_mode='HTML',
                    reply_markup=markup
                )
            except Exception as e:
                pass

        @bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_"))
        def confirm_game(call):
            try:
                user_id = call.from_user.id
                game_type, amount = call.data.split("_")[1], int(call.data.split("_")[2])
                username = call.from_user.username or "NoUsername"
                user_data = db.get(User.user_id == user_id)
                
                new_balance = user_data['balance'] - amount
                new_bets_count = user_data['bets_count'] + 1
                db.update({'balance': new_balance, 'bets_count': new_bets_count}, User.user_id == user_id)
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"Канал со ставками - <a href='{CHANNEL_LINK}'>тык</a>",
                    parse_mode='HTML'
                )
                
                game_text = "Больше" if game_type == "more" else "Меньше"
                channel_msg = bot.send_message(
                    CHANNEL_ID,
                    f"<b>Новая ставка</b>\n\n"
                    f"<blockquote><b>Игрок: @{username}</b></blockquote>\n"
                    f"<blockquote><b>Сумма ставки: {amount} звёзд</b></blockquote>\n"
                    f"<blockquote><b>Исход: {game_text}</b></blockquote>",
                    parse_mode='HTML'
                )
                
                time.sleep(1)
                dice = bot.send_dice(CHANNEL_ID)
                dice_value = dice.dice.value
                
                time.sleep(3)
                
                win = (game_type == "more" and dice_value in [4, 5, 6]) or \
                      (game_type == "less" and dice_value in [1, 2, 3])
                
                markup = types.InlineKeyboardMarkup()
                bet_button = types.InlineKeyboardButton("Сделать ставку", url=f"https://t.me/{BOT_USERNAME}?start=bet")
                markup.add(bet_button)
                      
                if win:
                    win_amount = amount * 2
                    new_balance = user_data['balance'] - amount + win_amount
                    new_total_earned = user_data['total_earned'] + win_amount
                    db.update({
                        'balance': new_balance,
                        'total_earned': new_total_earned
                    }, User.user_id == user_id)
                    
                    bot.send_message(
                        CHANNEL_ID,
                        f"<b>Победа! Выпало значение {dice_value}</b>\n\n"
                        f"<blockquote><b>На ваш баланс был зачислен выигрыш {win_amount} звёзд.</b></blockquote>",
                        parse_mode='HTML',
                        reply_markup=markup
                    )
                    bot.send_message(
                        user_id,
                        f"🎉 Вы выиграли! Выпало: {dice_value}\nВаш выигрыш: {win_amount} звёзд"
                    )
                else:
                    bot.send_message(
                        CHANNEL_ID,
                        f"<b>Вы проиграли. Попробуйте снова!</b>",
                        parse_mode='HTML',
                        reply_markup=markup
                    )
                    bot.send_message(
                        user_id,
                        f"😞 Вы проиграли. Выпало: {dice_value}"
                    )
            except Exception as e:
                bot.send_message(call.message.chat.id, "Произошла ошибка во время игры")

        @bot.callback_query_handler(func=lambda call: call.data == "cancel")
        def cancel_game(call):
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="Ставка отменена"
                )
            except Exception as e:
                pass

        @bot.message_handler(func=lambda message: message.text == "⚡️ Профиль")
        def profile_handler(message):
            try:
                user_id = message.from_user.id
                user_data = db.get(User.user_id == user_id)
                username = message.from_user.username or "NoUsername"
                
                text = "🎲 <b>Профиль</b>\n"
                text += f"👉🏼 ID: <code>{user_id}</code>\n"
                text += f"💰 Баланс: <code>{user_data['balance']} звёзд</code>\n"
                text += f"⚙ Никнейм: <code>{user_data['first_name']} {user_data['last_name']}</code>\n"
                text += f"🎮 Юзернейм: <code>@{username}</code>\n\n"
                text += "📊 Статистика:\n"
                text += f"💎 Ставок: <code>{user_data['bets_count']}</code>\n"
                text += f"💸 Ставки за все время: <code>{user_data['total_earned']} звёзд</code>\n"
                text += f"📆 Дата регистрации: <code>{user_data['reg_date']}</code>"
                
                bot.send_message(message.chat.id, text, parse_mode='HTML')
            except Exception as e:
                bot.send_message(message.chat.id, "Ошибка при загрузке профиля")

        @bot.message_handler(func=lambda message: message.text == "💰 Пополнить звёзды")
        def add_stars_handler(message):
            try:
                bot.send_message(message.chat.id,
                               "<b>Введите сколько хотите звезд пополнить на баланс</b>",
                               parse_mode='HTML')
                bot.register_next_step_handler(message, process_payment_amount)
            except Exception as e:
                pass

        def process_payment_amount(message):
            try:
                user_id = message.from_user.id
                amount = int(message.text)
                if amount <= 0:
                    bot.send_message(message.chat.id, "<b>Введите положительное число</b>")
                    return
                bot.send_invoice(
                    chat_id=message.chat.id,
                    title="Пополнение звёзд",
                    description=f"Пополнение на {amount} звёзд",
                    invoice_payload=f"payment_{user_id}_{amount}",
                    provider_token="",
                    currency="XTR",
                    prices=[types.LabeledPrice(label="Stars", amount=amount)]
                )
            except ValueError:
                bot.send_message(message.chat.id, "<b>Введите число</b>")
            except Exception as e:
                bot.send_message(message.chat.id, "Ошибка при обработке платежа")

        @bot.pre_checkout_query_handler(func=lambda query: True)
        def process_pre_checkout_query(pre_checkout_query):
            try:
                bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
            except Exception as e:
                pass

        @bot.message_handler(content_types=['successful_payment'])
        def process_successful_payment(message):
            try:
                user_id = message.from_user.id
                amount = message.successful_payment.total_amount
                user_data = db.get(User.user_id == user_id)
                new_balance = user_data['balance'] + amount
                db.update({'balance': new_balance}, User.user_id == user_id)
                bot.send_message(message.chat.id, f"<b>✅ Счёт успешно оплачен.\n\n💰 На баланс зачислено {amount} звёзд.</b>")
            except Exception as e:
                pass

        return bot

    except Exception as e:
        return None

def run_bot():
    global BOT_USERNAME  
    while True:
        try:
            bot = create_bot()
            if bot is None:
                raise Exception("test")
            
            bot.polling(none_stop=True, timeout=60)
            
        except Exception as e:
            print(f"произошла ошибка {str(e)}")
            print("перезапуск бота 5 сек")
            time.sleep(5)
            continue

if __name__ == "__main__":
    run_bot()