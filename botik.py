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

# Функционал для работы с пользователями и профилями

def register_user(message, username, password):
    user_id = message.from_user.id
    cursor.execute('SELECT * FROM profiles WHERE username=?', (username,))
    result = cursor.fetchone()

    if result is not None:
        bot.send_message(message.chat.id, "Пользователь с таким именем уже существует!")
        return False

    cursor.execute('INSERT INTO profiles (user_id, username, password) VALUES (?, ?,?)', (user_id,username, password))
    conn.commit()

    # Создаем профиль для нового пользователя

    bot.send_message(message.chat.id, "Регистрация прошла успешно!")
    return True

def login_user(message,username, password):
    cursor.execute('SELECT * FROM profiles WHERE username=? AND password=?', (username, password))
    result = cursor.fetchone()
    user_id=result[0]
    if result is None:
        bot.send_message(message.chat.id, "Неверное имя пользователя или пароль!")
        return False

    bot.send_message(message.chat.id, "Вы вошли в систему!")
    return user_id

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

def get_recommendations_with_profile(message,game_names, user_id, n_recommendations=3):
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
        if i not in indices and df_games.iloc[i]['name'] not in disliked_games
    ]

    # Сортируем оставшиеся игры по схожести
    sorted_scores = sorted(
        [(i, average_similarity[i]) for i in recommended_indices],
        key=lambda x: x[1],
        reverse=True
    )

    # Получаем топ-3 похожих настольных игры
    top_indices = [i[0] for i in sorted_scores[:n_recommendations]]
    recommendations = df_games.iloc[top_indices][['name']]

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

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я помогу вам найти интересные настольные игры. Начнем?")

@bot.message_handler(commands=['register'])
def handle_register(message):
    args = message.text.split(maxsplit=2)
    if len(args) != 3:
        bot.reply_to(message, "Неправильный формат команды. Используйте: /register <username> <password>")
        return
    username, password = args[1], args[2]
    if register_user(message, username, password):
        bot.reply_to(message, "Регистрация прошла успешно!")
    else:
        bot.reply_to(message, "Что-то пошло не так. Попробуйте снова.")

@bot.message_handler(commands=['login'])
def handle_login(message):
    args = message.text.split(maxsplit=2)
    if len(args) != 3:
        bot.reply_to(message, "Неправильный формат команды. Используйте: /login <username> <password>")
        return
    username, password = args[1], args[2]
    res=login_user(message, username, password)
    if res==False:

        bot.reply_to(message, "Неверное имя пользователя или пароль. Попробуйте снова.")
    else:
        bot.reply_to(message, "Вы успешно вошли в аккаунт.")
@bot.message_handler(commands=['description'])
def descr(message):
    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        bot.reply_to(message, "Неправильный формат команды. Используйте: /description <game_name>")
        return
    game_name = args[1]

    bot.reply_to(message, description(game_name))


@bot.message_handler(commands=['add_like'])
def handle_add_like(message):
    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        bot.reply_to(message, "Неправильный формат команды. Используйте: /add_like <game_name>")
        return
    game_name = args[1]
    user_id = message.from_user.id
    add_liked_game(message, user_id, game_name)

@bot.message_handler(commands=['add_dislike'])
def handle_add_dislike(message):
    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        bot.reply_to(message, "Неправильный формат команды. Используйте: /add_dislike <game_name>")
        return
    game_name = args[1]
    user_id = message.from_user.id
    add_disliked_game(message,user_id, game_name)

@bot.message_handler(commands=['show_likes'])
def handle_show_likes(message):
    user_id = message.from_user.id
    show_liked_games(message,user_id)

@bot.message_handler(commands=['show_dislikes'])
def handle_show_dislikes(message):
    user_id = message.from_user.id
    show_disliked_games(message,user_id)

@bot.message_handler(commands=['remove_like'])
def handle_remove_like(message):
    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        bot.reply_to(message, "Неправильный формат команды. Используйте: /remove_like <game_name>")
        return
    game_name = args[1]
    user_id = message.from_user.id
    remove_liked_game(message,user_id, game_name)

@bot.message_handler(commands=['remove_dislike'])
def handle_remove_dislike(message):
    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        bot.reply_to(message, "Неправильный формат команды. Используйте: /remove_dislike <game_name>")
        return
    game_name = args[1]
    user_id = message.from_user.id
    remove_disliked_game(message,user_id, game_name)

@bot.message_handler(commands=['get_recommendations'])
def handle_get_recommendations(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message,
                     "Неправильный формат команды. Используйте: /get_recommendations <game_name1> <game_name2> ...")
        return
    game_names = args[1:]
    user_id = message.from_user.id
    get_recommendations_with_profile(message,game_names, user_id)
bot.infinity_polling()