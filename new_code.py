import pandas as pd
import sqlite3
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from sklearn.metrics.pairwise import cosine_similarity
import ast

# Подключение к базе данных
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Создание таблиц, если они еще не существуют
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
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

def register_user(username, password):
    cursor.execute('SELECT * FROM users WHERE username=?', (username,))
    result = cursor.fetchone()

    if result is not None:
        print("Пользователь с таким именем уже существует!")
        return False

    cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
    conn.commit()

    # Создаем профиль для нового пользователя
    cursor.execute('INSERT INTO profiles (user_id) VALUES ((SELECT user_id FROM users WHERE username=?))', (username,))
    conn.commit()

    print("Регистрация прошла успешно!")
    return True


def login_user(username, password):
    cursor.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
    result = cursor.fetchone()

    if result is None:
        print("Неверное имя пользователя или пароль!")
        return False

    print("Вы вошли в систему!")
    return True


def add_liked_game(user_id, game_name):
    cursor.execute('UPDATE profiles SET liked_games = liked_games || ? WHERE user_id = ?', ('|' + game_name, user_id))
    conn.commit()
    print(f"Игра '{game_name}' добавлена в список понравившихся!")


def add_disliked_game(user_id, game_name):
    cursor.execute('UPDATE profiles SET disliked_games = disliked_games || ? WHERE user_id = ?',
                   ('|' + game_name, user_id))
    conn.commit()
    print(f"Игра '{game_name}' добавлена в список непонравившихся!")


def get_profile_data(user_id):
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,))
    return cursor.fetchone()


# Функционал для получения рекомендаций

def get_indices(game_names):
    indices = []
    for name in game_names:
        try:
            index = df_games[df_games['name'] == name].index[0]
            indices.append(index)
        except IndexError:
            print(f"Настольная игра '{name}' не найдена.")
    return indices

#Косинусная схожесть
def get_average_cosine_similarity(indices):
    average_similarity = cosine_sim[indices].mean(axis=0)
    return average_similarity
#список понравившихся игр
def show_liked_games(user_id):
    profile_data = get_profile_data(user_id)
    liked_games = profile_data[2].strip('|').split('|') if profile_data[2] else []
    if liked_games:
        print("\nСписок ваших понравившихся игр:")
        for i, game in enumerate(liked_games, start=1):
            print(f"{i}. {game}")
    else:
        print("\nУ вас пока нет понравившихся игр.")
#непонравившихся
def show_disliked_games(user_id):
    profile_data = get_profile_data(user_id)
    disliked_games = profile_data[3].strip('|').split('|') if profile_data[3] else []
    if disliked_games:
        print("\nСписок ваших непонравившихся игр:")
        for i, game in enumerate(disliked_games, start=1):
            print(f"{i}. {game}")
    else:
        print("\nУ вас пока нет непонравившихся игр.")


def remove_liked_game(user_id, game_name):
    profile_data = get_profile_data(user_id)
    liked_games = profile_data[2].strip('|').split('|') if profile_data[2] else []

    if game_name in liked_games:
        liked_games.remove(game_name)
        updated_liked_games = '|'.join(liked_games)
        cursor.execute('UPDATE profiles SET liked_games = ? WHERE user_id = ?', (updated_liked_games, user_id))
        conn.commit()
        print(f"Игра '{game_name}' удалена из списка понравившихся.")
    else:
        print(f"Игра '{game_name}' не найдена в списке понравившихся.")


def remove_disliked_game(user_id, game_name):
    profile_data = get_profile_data(user_id)
    disliked_games = profile_data[3].strip('|').split('|') if profile_data[3] else []

    if game_name in disliked_games:
        disliked_games.remove(game_name)
        updated_disliked_games = '|'.join(disliked_games)
        cursor.execute('UPDATE profiles SET disliked_games = ? WHERE user_id = ?', (updated_disliked_games, user_id))
        conn.commit()
        print(f"Игра '{game_name}' удалена из списка непонравившихся.")
    else:
        print(f"Игра '{game_name}' не найдена в списке непонравившихся.")
#реки
def get_recommendations_with_profile(game_names, user_id, n_recommendations=3):
    # Получаем данные профиля
    profile_data = get_profile_data(user_id)
    liked_games = profile_data[2].strip('|').split('|') if profile_data[2] else []
    disliked_games = profile_data[3].strip('|').split('|') if profile_data[3] else []

    # Получаем индексы любимых игр
    liked_indices = get_indices(liked_games)

    # Учитываем предпочтения пользователя при фильтрации рекомендаций
    indices = get_indices(game_names)

    if not indices:
        print("Все указанные настольные игры не найдены.")
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
    return df_games.iloc[top_indices][['name']]



    # Основная логика программы


while True:
    print("\nМеню:")
    print("1. Регистрация")
    print("2. Вход")
    print("3. Выход")

    choice = input("Ваш выбор: ")

    if choice == '1':
        username = input("Введите имя пользователя: ")
        password = input("Введите пароль: ")

        if register_user(username, password):
            print("Теперь вы можете войти в систему.")

    elif choice == '2':
        username = input("Введите имя пользователя: ")
        password = input("Введите пароль: ")

        if login_user(username, password):
            break
        else:
            continue

    elif choice == '3':
        exit()

    else:
        print("Неверный ввод! Попробуйте снова.")

    # Получаем ID текущего пользователя
cursor.execute('SELECT user_id FROM users WHERE username=?', (username,))
user_id = cursor.fetchone()[0]
while True:
        print("\nМеню:")
        print("1. Показать понравившиеся игры")
        print("2. Показать непонравившиеся игры")
        print("3. Удалить игру из списка понравившихся")
        print("4. Удалить игру из списка непонравившихся")
        print("5. Рекомендации по настольным играм")
        print("6. Выход")

        choice = input("Ваш выбор: ")

        if choice == '1':
            show_liked_games(user_id)
        elif choice == '2':
            show_disliked_games(user_id)
        elif choice == '3':
            game_name = input("Введите название игры, которую хотите удалить из списка понравившихся: ")
            remove_liked_game(user_id, game_name)
        elif choice == '4':
            game_name = input("Введите название игры, которую хотите удалить из списка непонравившихся: ")
            remove_disliked_game(user_id, game_name)
        elif choice == '5':
            print("\nВас приветствует рекомендательная система настольных игр Nastolkin.")
            print("Пожалуйста, введите названия настольных игр через запятую:")
            game_names = input().split(',')
            n = int(input("Сколько рекомендаций вы хотите(по стандарту 3)?\n"))
            recommendations = get_recommendations_with_profile(game_names, user_id, n)
            print(recommendations)
        elif choice == '6':
            break
        else:
            print("Неверный ввод! Попробуйте снова.")