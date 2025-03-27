import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from sklearn.metrics.pairwise import cosine_similarity
import ast

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


# Функция для получения индексов игр по названиям
def get_indices(game_names):
    indices = []
    for name in game_names:
        try:
            index = df_games[df_games['name'] == name].index[0]
            indices.append(index)
        except IndexError:
            print(f"Настольная игра '{name}' не найдена.")
    return indices


# Функция для получения среднего значения косинусной схожести
def get_average_cosine_similarity(indices):
    average_similarity = cosine_sim[indices].mean(axis=0)
    return average_similarity


# Функция для получения рекомендаций
def get_recommendations(game_names, n_recommendations=3):
    indices = get_indices(game_names)

    if not indices:
        print("Все указанные настольные игры не найдены.")
        return None

    # Вычисляем среднее значение косинусной схожести
    average_similarity = get_average_cosine_similarity(indices)

    # Исключаем сами введённые игры из рекомендаций
    recommended_indices = [i for i, sim in enumerate(average_similarity) if i not in indices]

    # Сортируем оставшиеся игры по схожести
    sorted_scores = sorted(
        [(i, average_similarity[i]) for i in recommended_indices],
        key=lambda x: x[1],
        reverse=True
    )

    # Получаем топ-3 похожих настольных игры

    top_indices = [i[0] for i in sorted_scores[:n_recommendations]]
    return df_games.iloc[top_indices][['name']]


# Пример использования функции
print("Вас приветствует рекомендательная система настольных игр Nastolkin.")
print("Пожалуйста, введите названия настольных игр через запятую:")
game_names = input().split(',')
n = int(input("Сколько рекомендаций вы хотите(по стандарту 3)?\n"))
print(get_recommendations(game_names, n))
