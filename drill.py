import telebot
import pandas as pd
import sqlite3
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from sklearn.metrics.pairwise import cosine_similarity
import ast


API = '7985853025:AAEOIJvCdF2zX_bQnxgvqZd5AmElV0VzD2E'
# Подключение к базе данных
conn = sqlite3.connect('profile.db', check_same_thread=False)
cursor = conn.cursor()
global message
# Создание таблиц, если они еще не существуют

user_state = {}
cursor.execute('''
CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    
    
    liked_games TEXT DEFAULT '',
    disliked_games TEXT DEFAULT '',
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);
''')

conn.commit()

# Чтение данных из CSV файла
df_games = pd.read_csv('modified_boardgames.csv')
for col in ['boardgamecategory', 'boardgamemechanic']:
    df_games[col] = df_games[col].apply(ast.literal_eval)

# Объединение всех признаков в одну строку для векторизации
def combine_features(row):
    return f"{row['yearpublished']} {row['minplayers']} {row['maxplayers']} {row['minplaytime']} {row['maxplaytime']} {row['playerage']} {row['boardgamecategory']} {row['boardgamemechanic']}"

df_games['combined_features'] = df_games.apply(combine_features, axis=1)

# Векторизация комбинированных признаков
count_vect = CountVectorizer(stop_words='english')
count_matrix = count_vect.fit_transform(df_games['combined_features'].values.astype(str))

# Преобразование частотных векторов в TF-IDF матрицу
tfidf_transformer = TfidfTransformer()
tfidf_matrix = tfidf_transformer.fit_transform(count_matrix)

# Вычисление косинусной схожести между настольными играми
cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

def add_liked_game(message,user_id, game_name):
    cursor.execute('UPDATE profiles SET liked_games = liked_games || ? WHERE user_id = ?', ('|' + game_name, user_id))
    conn.commit()
    bot.send_message(message.chat.id, f"Игра '{game_name}' добавлена в список понравившихся!")

def add_disliked_game(message,user_id, game_name):
    cursor.execute('UPDATE profiles SET disliked_games = disliked_games || ? WHERE user_id = ?', ('|' + game_name, user_id))
    conn.commit()
    bot.send_message(message.chat.id, f"Игра '{game_name}' добавлена в список непонравившихся!")

def get_profile_data(user_id):
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

# Функционал для получения рекомендаций
def get_indices(message, game_names):
    indices = []
    for name in game_names:
        try:
            index = df_games[df_games['name'] == name].index[0]
            indices.append(index)
        except IndexError:
            bot.send_message(message.chat.id, f"Настольная игра '{name}' не найдена.")
    return indices

def get_average_cosine_similarity(indices):
    average_similarity = cosine_sim[indices].mean(axis=0)
    return average_similarity

def show_liked_games(message,user_id):
    profile_data = get_profile_data(user_id)
    try:
        liked_games = profile_data[3].strip('|').split('|') if profile_data[3] else []
        if liked_games:
            bot.send_message(message.chat.id, "\nСписок ваших понравившихся игр:")
            for i, game in enumerate(liked_games, start=1):
                bot.send_message(message.chat.id, f"{i}. {game}")
        else:
            bot.send_message(message.chat.id, "\nУ вас пока нет понравившихся игр.")
    except TypeError:
        bot.send_message(message.chat.id, "Ваш список пуст")

def show_disliked_games(message,user_id):
    profile_data = get_profile_data(user_id)
    disliked_games = profile_data[4].strip('|').split('|') if profile_data[4] else []
    if disliked_games:
        bot.send_message(message.chat.id, "\nСписок ваших непонравившихся игр:")
        for i, game in enumerate(disliked_games, start=1):
            bot.send_message(message.chat.id, f"{i}. {game}")
    else:
        bot.send_message(message.chat.id, "\nУ вас пока нет непонравившихся игр.")

def remove_liked_game(message,user_id, game_name):
    profile_data = get_profile_data(user_id)
    liked_games = profile_data[3].strip('|').split('|') if profile_data[3] else []

    if game_name in liked_games:
        liked_games.remove(game_name)
        updated_liked_games = '|'.join(liked_games)
        cursor.execute('UPDATE profiles SET liked_games = ? WHERE user_id = ?', (updated_liked_games, user_id))
        conn.commit()
        bot.send_message(message.chat.id, f"Игра '{game_name}' удалена из списка понравившихся.")
    else:
        bot.send_message(message.chat.id, f"Игра '{game_name}' не найдена в списке понравившихся.")

def remove_disliked_game(message,user_id, game_name):
    profile_data = get_profile_data(user_id)
    disliked_games = profile_data[4].strip('|').split('|') if profile_data[4] else []

    if game_name in disliked_games:
        disliked_games.remove(game_name)
        updated_disliked_games = '|'.join(disliked_games)
        cursor.execute('UPDATE profiles SET disliked_games = ? WHERE user_id = ?', (updated_disliked_games, user_id))
        conn.commit()
        bot.send_message(message.chat.id, f"Игра '{game_name}' удалена из списка непонравившихся.")
    else:
        bot.send_message(message.chat.id, f"Игра '{game_name}' не найдена в списке непонравившихся.")

def get_recommendations_with_profile(message,game_names, user_id, n_recommendations=5):
    # Получаем данные профиля
    profile_data = get_profile_data(user_id)
    liked_games = profile_data[3].strip('|').split('|') if profile_data[3] else []
    disliked_games = profile_data[4].strip('|').split('|') if profile_data[4] else []

    # Получаем индексы любимых игр
    liked_indices = get_indices(message, liked_games)

    # Учитываем предпочтения пользователя при фильтрации рекомендаций
    indices = get_indices(message, game_names)

    if not indices:
        bot.send_message(message.chat.id, "Все указанные настольные игры не найдены.")
        return None

    # Вычисляем среднее значение косинусной схожести
    if liked_indices:
        # Если есть любимые игры, добавляем их в расчет схожести
        all_indices = indices + liked_indices
        average_similarity = get_average_cosine_similarity(all_indices)
    else:
        # Если нет любимых игр, рассчитываем только по введенным играм
        average_similarity = get_average_cosine_similarity(indices)

    # Применяем штрафной коэффициент для непонравившихся игр
    for idx, sim in enumerate(average_similarity):
        if df_games.iloc[idx]['name'] in disliked_games:
            average_similarity[idx] *= 0.25  # Штрафуем непонравившиеся игры

# Исключаем сами введённые игры и игры из списка неприязни
    recommended_indices = [
        i for i, sim in enumerate(average_similarity)
        if i not in indices and df_games.iloc[i]['name'] not in disliked_games and i not in liked_indices
    ]

    # Сортируем оставшиеся игры по схожести
    sorted_scores = sorted(
        [(i, average_similarity[i]) for i in recommended_indices],
        key=lambda x: x[1],
        reverse=True
    )

    # Получаем топ-3 похожих настольных игры
    top_indices = [i[0] for i in sorted_scores[:n_recommendations]]
    recommendations = df_games.iloc[top_indices][['name','boardgamecategory','boardgamemechanic']]

    bot.send_message(message.chat.id, f"Вот рекомендации для вас:\n{recommendations.to_string()}")
    return recommendations
def description(game_name):
    try:

        return df_games.loc[df_games['name'] == game_name, 'description'].values[0]
    except:
        return 'Такой игры нет в нашем каталоге'
# Основной код бота
API_TOKEN = '7985853025:AAEOIJvCdF2zX_bQnxgvqZd5AmElV0VzD2E'  # Замените на ваш токен
bot = telebot.TeleBot(API_TOKEN)

keyboard = telebot.types.ReplyKeyboardMarkup(row_width=3)
button_1 = telebot.types.KeyboardButton('Добавить любимую')
button_2 = telebot.types.KeyboardButton('Добавить нелюбимую')
button_3 = telebot.types.KeyboardButton('Список любимых')
button_4 = telebot.types.KeyboardButton('Список нелюбимых')
button_5 = telebot.types.KeyboardButton('Убрать любимую')
button_6 = telebot.types.KeyboardButton('Убрать нелюбимую')
button_7 = telebot.types.KeyboardButton('Рекомендации')
button_8 = telebot.types.KeyboardButton('Главное меню')
button_9 = telebot.types.KeyboardButton('Описание')
keyboard.add(button_1,button_2,button_3)
keyboard.add(button_4,button_5,button_6)
keyboard.add(button_7,button_8,button_9)
# Создаем ReplyKeyboardMarkup с нужными параметрами

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я помогу вам найти интересные настольные игры. Начнем?", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == 'Меню')
def send_welcome(message):

    bot.reply_to(message, "Привет! Добро пожаловать в главное меню. Я помогу вам найти интересные настольные игры. Начнем?", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == 'Описание')
def descr(message):
    bot.reply_to(message, "Пожалуйста, введите название игры", reply_markup=keyboard)

    user_state[message.from_user.id] = 'desc'


@bot.message_handler(func=lambda message: message.text == 'Добавить любимую')
def handle_add_like(message):


    bot.reply_to(message, "Пожалуйста, введите название игры",reply_markup=keyboard)

    user_state[message.from_user.id] = 'awaiting_game_name'



@bot.message_handler(func=lambda message: message.text == 'Добавить нелюбимую')
def handle_add_dislike(message):
    bot.reply_to(message, "Пожалуйста, введите название игры",reply_markup=keyboard)

    user_state[message.from_user.id] = 'disawaiting_game_name'


@bot.message_handler(func=lambda message: message.text == 'Список любимых')
def handle_show_likes(message):
    user_id = message.from_user.id
    show_liked_games(message,user_id)

@bot.message_handler(func=lambda message: message.text == 'Список нелюбимых')
def handle_show_dislikes(message):
    user_id = message.from_user.id
    show_disliked_games(message,user_id)

@bot.message_handler(func=lambda message: message.text == 'Убрать любимую')
def handle_remove_like(message):
    bot.reply_to(message, "Пожалуйста, введите название игры",reply_markup=keyboard)

    user_state[message.from_user.id] = 'del_love'


@bot.message_handler(func=lambda message: message.text == 'Убрать нелюбимую')
def handle_remove_dislike(message):
    bot.reply_to(message, "Пожалуйста, введите название игры",reply_markup=keyboard)

    user_state[message.from_user.id] = 'del_unlove'

@bot.message_handler(func=lambda message: message.text == 'Рекомендации')
def handle_get_recommendations(message):
    bot.reply_to(message, "Пожалуйста, вводите названия игр(через запятую без пробелов)",reply_markup=keyboard)

    user_state[message.from_user.id] = 'recs'



#,reply_markup=keyboard
@bot.message_handler(func=lambda message: message.content_type == 'text')
def handle_user_input(message):
    user_id = message.from_user.id

    if user_id in user_state and user_state[user_id] == 'awaiting_game_name':

        add_liked_game(message, user_id, message.text)

        bot.send_message(user_id, f'Игра "{message.text}" была успешно добавлена в базу данных.', reply_markup=keyboard)

        del user_state[user_id]
    elif user_id in user_state and user_state[user_id] == 'disawaiting_game_name':

        add_disliked_game(message, user_id, message.text)
        bot.send_message(user_id, f'Игра "{message.text}" была успешно добавлена в базу данных.', reply_markup=keyboard)

        del user_state[user_id]
    elif user_id in user_state and user_state[user_id] == 'del_love':

        remove_liked_game(message,user_id, message.text)
        bot.send_message(user_id, f'Игра "{message.text}" была успешно удалена из базы данных.', reply_markup=keyboard)

        del user_state[user_id]
    elif user_id in user_state and user_state[user_id] == 'del_unlove':

        remove_disliked_game(message,user_id, message.text)
        bot.send_message(user_id, f'Игра "{message.text}" была успешно удалена из базы данных.', reply_markup=keyboard)

        del user_state[user_id]
    elif user_id in user_state and user_state[user_id] == 'recs':

        game_names=message.text.split(',')
        get_recommendations_with_profile(message,game_names, user_id)


        del user_state[user_id]
    elif user_id in user_state and user_state[user_id] == 'desc':
        bot.send_message(user_id, description(message.text), reply_markup=keyboard)

        del user_state[user_id]
bot.infinity_polling()