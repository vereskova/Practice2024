import telebot
from telebot import types
import datetime
import os
import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler

# Токен, отриманий від BotFather, додано до середи оточення
TOKEN = os.getenv('BOTAPI')
bot = telebot.TeleBot(TOKEN)

# Ініціалізація планувальника
scheduler = BackgroundScheduler()
scheduler.start()

# Ініціалізація бази даних
def init_db():
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY,
                        chat_id INTEGER NOT NULL,
                        task TEXT NOT NULL,
                        done BOOLEAN NOT NULL,
                        reminder_time DATETIME)''')
    conn.commit()
    conn.close()

# Виклик ініціалізації бази даних
init_db()

# Обробник команди /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привіт! Я бот для управління завданнями. Використовуйте /new для створення нового завдання.")

# Обробник команди /new
@bot.message_handler(commands=['new'])
def new_task(message):
    chat_id = message.chat.id
    msg = bot.reply_to(message, 'Введіть завдання:')
    bot.register_next_step_handler(msg, lambda m: save_task(chat_id, m))

# Збереження нового завдання в базу даних
def save_task(chat_id, message):
    task = message.text
    if task:
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO tasks (chat_id, task, done, reminder_time) VALUES (?, ?, ?, ?)',
                       (chat_id, task, False, None))
        conn.commit()
        conn.close()
        bot.reply_to(message, f'Завдання "{task}" створено!')
    else:
        bot.reply_to(message, 'Будь ласка, уточніть завдання.')

# Обробник команди /list для відображення всіх завдань
@bot.message_handler(commands=['list'])
def list_tasks(message):
    chat_id = message.chat.id
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, task, done FROM tasks WHERE chat_id = ?', (chat_id,))
    tasks = cursor.fetchall()
    conn.close()

    if tasks:
        task_list = '\n'.join([f"{idx + 1}. {'[X]' if task[2] else '[ ]'} {task[1]}" for idx, task in enumerate(tasks)])
        bot.reply_to(message, f'Ваш список завдань:\n{task_list}')
    else:
        bot.reply_to(message, 'У вас немає активних завдань.')

# Обробник команди /done для відмітки завдання як виконаного
@bot.message_handler(commands=['done'])
def done_task(message):
    chat_id = message.chat.id
    msg = bot.reply_to(message, 'Введіть номер виконаного завдання:')
    bot.register_next_step_handler(msg, lambda m: mark_task_done(chat_id, m))

# Відмітка завдання як виконаного в базі даних
def mark_task_done(chat_id, message):
    try:
        task_id = int(message.text) - 1
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, task FROM tasks WHERE chat_id = ?', (chat_id,))
        tasks = cursor.fetchall()

        if 0 <= task_id < len(tasks):
            task = tasks[task_id]
            cursor.execute('UPDATE tasks SET done = ? WHERE id = ?', (True, task[0]))
            conn.commit()
            conn.close()
            bot.reply_to(message, f'Завдання "{task[1]}" відмічено як виконане!')
        else:
            bot.reply_to(message, 'Невірний номер завдання або у вас немає завдань.')
    except ValueError:
        bot.reply_to(message, 'Будь ласка, введіть дійсний номер завдання.')

# Обробник команди /delete для видалення завдання
@bot.message_handler(commands=['delete'])
def delete_task(message):
    chat_id = message.chat.id
    msg = bot.reply_to(message, 'Введіть номер завдання для видалення:')
    bot.register_next_step_handler(msg, lambda m: remove_task(chat_id, m))

# Видалення завдання з бази даних
def remove_task(chat_id, message):
    try:
        task_id = int(message.text) - 1
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, task FROM tasks WHERE chat_id = ?', (chat_id,))
        tasks = cursor.fetchall()

        if 0 <= task_id < len(tasks):
            task = tasks[task_id]
            cursor.execute('DELETE FROM tasks WHERE id = ?', (task[0],))
            conn.commit()
            conn.close()
            bot.reply_to(message, f'Завдання "{task[1]}" видалено!')
        else:
            bot.reply_to(message, 'Невірний номер завдання або у вас немає завдань.')
    except ValueError:
        bot.reply_to(message, 'Будь ласка, введіть дійсний номер завдання.')

# Обробник команди /reminder для встановлення нагадування
@bot.message_handler(commands=['reminder'])
def reminder_message(message):
    chat_id = message.chat.id
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, task FROM tasks WHERE chat_id = ?', (chat_id,))
    tasks = cursor.fetchall()
    conn.close()

    if tasks:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for idx, task in enumerate(tasks):
            task_text = f"{idx + 1}. {task[1]}"
            keyboard.add(types.KeyboardButton(task_text))

        msg = bot.send_message(chat_id, "Виберіть завдання для встановлення нагадування:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, lambda m: choose_intervals(chat_id, m))
    else:
        bot.send_message(chat_id, 'У вас немає активних завдань.')

# Вибір інтервалу часу для нагадування
def choose_intervals(chat_id, message):
    try:
        task_id = int(message.text.split('.')[0]) - 1
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, task FROM tasks WHERE chat_id = ?', (chat_id,))
        tasks = cursor.fetchall()
        if 0 <= task_id < len(tasks):
            task = tasks[task_id]
            intervals = ['Роки', 'Місяці', 'Тижні', 'Дні', 'Години', 'Хвилини', 'Секунди']
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            for interval in intervals:
                keyboard.add(types.InlineKeyboardButton(interval, callback_data=f'{interval}_{task[0]}_0'))
            bot.send_message(chat_id, 'Оберіть часовий інтервал:', reply_markup=keyboard)
        else:
            bot.send_message(chat_id, 'Будь ласка, виберіть дійсне завдання для встановлення нагадування.')
    except (IndexError, ValueError):
        bot.send_message(chat_id, 'Будь ласка, виберіть дійсне завдання для встановлення нагадування.')

# Обробник натискання на клавіші інтервалу
@bot.callback_query_handler(func=lambda call: call.data)
def callback_inline(call):
    if call.message:
        data = call.data.split('_')
        interval, task_id, total_seconds = data[0], int(data[1]), int(data[2])

        if interval == 'Done':
            handle_reminder_set(call.message.chat.id, task_id, total_seconds)
        else:
            msg = bot.send_message(call.message.chat.id, f'Введіть кількість {interval.lower()}:')
            bot.register_next_step_handler(msg, lambda m: handle_interval_input(m, call, interval, task_id, total_seconds))

# Обробка введення інтервалу
def handle_interval_input(message, call, interval, task_id, total_seconds):
    try:
        delta = int(message.text)
        if interval == 'Роки':
            total_seconds += delta * 365 * 24 * 60 * 60
        elif interval == 'Місяці':
            total_seconds += delta * 30 * 24 * 60 * 60
        elif interval == 'Тижні':
            total_seconds += delta * 7 * 24 * 60 * 60
        elif interval == 'Дні':
            total_seconds += delta * 24 * 60 * 60
        elif interval == 'Години':
            total_seconds += delta * 60 * 60
        elif interval == 'Хвилини':
            total_seconds += delta * 60
        elif interval == 'Секунди':
            total_seconds += delta

        intervals = ['Роки', 'Місяці', 'Тижні', 'Дні', 'Години', 'Хвилини', 'Секунди']
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        for idx, interval in enumerate(intervals):
            keyboard.add(types.InlineKeyboardButton(interval, callback_data=f'{interval}_{task_id}_{total_seconds}'))
        keyboard.add(types.InlineKeyboardButton('Done', callback_data=f'Done_{task_id}_{total_seconds}'))

        bot.send_message(call.message.chat.id, 'Бажаєте додати ще один інтервал?', reply_markup=keyboard)
    except ValueError:
        bot.send_message(message.chat.id, 'Будь ласка, введіть дійсне число.')

# Встановлення нагадування для завдання
def handle_reminder_set(chat_id, task_id, total_seconds):
    now = datetime.datetime.now()
    reminder_time = now + datetime.timedelta(seconds=total_seconds)
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute('SELECT task FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    cursor.execute('UPDATE tasks SET reminder_time = ? WHERE id = ?', (reminder_time, task_id))
    conn.commit()
    conn.close()

    scheduler.add_job(send_reminder, 'date', run_date=reminder_time, args=[chat_id, task[0]])

    delta_message = str(datetime.timedelta(seconds=total_seconds))
    bot.send_message(chat_id, f'Чудово, ми нагадаємо вам про завдання "{task[0]}" через {delta_message}.')

# Відправлення нагадування
def send_reminder(chat_id, task_name):
    bot.send_message(chat_id, f'*НАГАДУВАННЯ!* Не забудьте виконати завдання "{task_name}"!')

# Запуск бота для обробки повідомлень
if __name__ == '__main__':
    bot.polling(none_stop=True)


