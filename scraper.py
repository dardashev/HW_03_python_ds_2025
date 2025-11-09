import time
import requests
import schedule
from bs4 import BeautifulSoup
from bs4.element import Tag
import re
from tqdm import tqdm
import threading
import json
import os

_number_pattern    = re.compile('[\d.]+') # Паттерн поиска числа
_rating_pattern    = re.compile('star-rating .*') # Паттерн поиска строкового значения рейтинги(One, Two, etc.)
_main_data_pattern = re.compile('.* product_main') # Паттерн поиска имени класса основных данных книги

def get_tag(context: Tag, tag_name: str, class_name: str|re.Pattern = '') -> Tag|None:
   """
   Находит объект Tag с указанным именем и классом в переданном контексте.
    
    Args:
        context (Tag): Объект bs4.element.Tag, в котором осуществляется поиск
        tag_name (str): Название HTML-тега для поиска (например, 'div', 'span', 'a')
        class_name (str|re.Pattern, optional): Название класса или регулярное выражение 
                                              для поиска по классу. По умолчанию ''.
    
    Returns:
        Tag|None: Первый найденный тег, соответствующий критериям, или None если тег не найден
                  или найденный объект не является тегом.
    """
  
   tag = context.find(tag_name, class_=class_name) if class_name else context.find(tag_name, class_=None) # type: ignore

   return tag if type(tag) == Tag else None


def _set_dict_value(data: dict[str, str|int|float], key: str, element: Tag|None, data_type: str) -> None:
   """
   Извлекает данные из Tag-элемента и добавляет их в словарь.
    
   Args:
      data (dict[str, str|int|float]): Словарь, в который добавляется значение
      key (str): Ключ для записи значения в словарь
      element (Tag|None): HTML-элемент BeautifulSoup Tag или None
      data_type (str): Тип извлекаемых данных: 'text', 'number' или 'rating'
    
   Returns:
      None: Функция модифицирует переданный словарь data
    
   Notes:
      - Для data_type 'text': извлекает текстовое содержимое элемента
      - Для data_type 'number': ищет числовое значение в тексте с помощью регулярного выражения
      - Для data_type 'rating': определяет рейтинг по второму слову в названии класса (0-5 звезд)
      - Если передан неверный аргумент element, значение в словаре не меняется
    """
   if not element:
      return
   elif data_type not in ('text', 'number', 'rating'):
      return
   elif data_type == 'text':
      data[key] = element.text.strip()
   elif data_type == 'number':
      match = re.search(_number_pattern, element.text)
      if match:
         data[key] = float(match.group()) if '.' in match.group() else int(match.group())
   elif data_type == 'rating':
      stars_count = ('zero', 'one', 'two', 'three', 'four', 'five')
      rating = element['class'][1].lower()
      if rating in stars_count:
         data[key] = stars_count.index(rating)


def get_rows(parent: Tag) -> dict[str, str]:
   """
    Извлекает данные из таблицы и возвращает в виде словаря.
    
    Args:
        parent: Родительский Tag-элемент, содержащий таблицу
    
    Returns:
        dict: Словарь, где ключи - тексты из ячеек <th>, 
              значения - тексты из соответствующих ячеек <td>
    """
   rows = {}
   for row in parent.find_all('tr'):
      if type(row) != Tag:
         continue
      key   = get_tag(row, 'th')
      value = get_tag(row, 'td')
      if key:
         _set_dict_value(rows, key.text, value, 'text')
         
   return rows


def get_book_data(book_url: str) -> dict[str, str|int|float|dict[str, str]]:
   """
    Извлекает данные о книге с веб-страницы.
    
    Args:
        book_url (str): URL-адрес страницы книги для парсинга
    
    Returns:
        dict: Словарь с данными о книге, содержащий:
            - title (str): Название книги
            - price (int|float): Цена книги
            - rating (int): Рейтинг от 0 до 5
            - available (int): Количество доступных экземпляров
            - description (str): Описание книги
            - additional_info (dict): Дополнительная информация из таблицы
    """

   data = {
      'title': '',
      'price': 0, 
      'rating': 0, 
      'available': 0, 
      'description': '', 
      'additional_info': {}
      }

   response = requests.get(book_url) 
   response.encoding = 'utf-8'

   # Выбрасывает исключение, если запрос неудачный (код начинается не с 2*)  
   response.raise_for_status()

   soup = BeautifulSoup(response.text, 'html.parser')

   data_root = get_tag(soup, 'article', 'product_page')

   if not data_root:
      return data

   main_data = get_tag(data_root , 'div', _main_data_pattern)

   if not main_data:
      return data

   title_elem        = get_tag(main_data, 'h1')
   description_elem  = get_tag(data_root, 'p')
   rating_elem       = get_tag(main_data, 'p', _rating_pattern)
   price_elem        = get_tag(main_data, 'p', 'price_color')
   available_elem    = get_tag(main_data, 'p', 'instock availability')

   _set_dict_value(data, 'title'       , title_elem      , 'text')
   _set_dict_value(data, 'description' , description_elem, 'text')
   _set_dict_value(data, 'price'       , price_elem      , 'number')
   _set_dict_value(data, 'available'   , available_elem  , 'number')
   _set_dict_value(data, 'rating'      , rating_elem     , 'rating')

   table = get_tag(data_root, 'table', 'table table-striped')

   if table:
      data['additional_info'] = get_rows(table)

   return data


# Корневая ссылка для парсинга и скрапинга книг
_root_url = 'https://books.toscrape.com/catalogue/'

def _get_page_soup(page_number: int) -> BeautifulSoup:
    """
    Получает HTML-страницу каталога и возвращает объект BeautifulSoup.
    
    Args:
        page_number (int): Номер страницы каталога для загрузки
    
    Returns:
        BeautifulSoup: Объект для парсинга HTML-страницы
    
    Raises:
        requests.HTTPError: Если HTTP-запрос завершился с ошибкой
    """
    response = requests.get(f'{_root_url}page-{page_number}.html')
    # Выбрасывает исключение, если запрос неудачный (код начинается не с 2*)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')


def _get_pages_count() -> int:
    """
    Определяет количество страниц в каталоге.
    
    Returns:
        int: Общее количество страниц или 0 при ошибке
    """
    try:
        soup = _get_page_soup(1)
    except:
        return 0
    
    counter_elem = get_tag(soup, 'li', 'current')
    
    if not counter_elem:
        return 0
    
    pattern = re.compile('of (\d+)')
    match = re.search(pattern, counter_elem.text)

    return int(match.group(1)) if match else 0


def _parse_page(page_number: int,  books_data: list[dict], pbar: tqdm|None = None) -> None:
    """
    Парсит страницу каталога и добавляет данные книг в список.
    Функция используется для работы в многопоточном режиме.
    
    Args:
        page_number (int): Номер страницы каталога для парсинга
        books_data (list[dict]): Список для добавления данных о книгах
        pbar (tqdm): Прогресс-бар для обновления статуса выполнения
    """
    try: 
        soup = _get_page_soup(page_number)
    except:
        return

    books_container = get_tag(soup, 'ol', 'row')

    if not books_container:
        return

    for heading in books_container.find_all('h3'):
        
        if type(heading) != Tag:
            continue
        
        link = get_tag(heading, 'a')
       
        if not link:
            continue
        
        href = link['href'] 

        if not href:
            continue

        url = _root_url + str(href)

        books_data.append(get_book_data(url))

    if pbar:
        pbar.update(1)


def scrape_books(is_save=False) -> list[dict]:
    """
    Собирает данные о всех книгах из каталога с использованием многопоточности.
    
    Args:
        is_save (bool, optional): Сохранять ли данные в файл. По умолчанию False.
    
    Returns:
        list[dict]: Список словарей с данными о книгах
    
    Process:
        - Определяет общее количество страниц в каталоге
        - Обрабатывает страницы параллельно в нескольких потоках
        - Сохраняет данные в файл при необходимости
        - Отображает прогресс выполнения через tqdm
    """
    # Количество потоков. В одном потоке обрабатывается одна страница
    threads_number = 25

    # Список, в который будут добавляться распрасенные данные книг
    books_data = []

    # Количество страниц
    pages_count = _get_pages_count()
    
    with tqdm(total=pages_count, desc='scraping pages') as pbar:

        for page_number in range(1, pages_count + 1, threads_number):
            
            threads = []

            for shift in range(threads_number):
                if page_number + shift > pages_count:
                    break
                threads.append(
                    threading.Thread(
                        target=_parse_page,
                        args=(page_number + shift, books_data, pbar))
                    ) 

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

    if is_save:
        # Получаем путь к директории исполняемого файла
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Формируем полный путь к файлу
        file_path = os.path.join(current_dir, 'books_data.txt')
        print(file_path)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(books_data, indent=4))

    return books_data


def run_autoscreping(start_time = '19:00', sleeping_time = 60) -> None:
    """
    Запускает автоматический парсинг книг по расписанию.
    
    Args:
        start_time (str): Время запуска парсинга в формате 'HH:MM'. По умолчанию '19:00'
        sleeping_time (int): Интервал проверки расписания в секундах. По умолчанию 60 секунд
    """
    schedule.every().day.at(start_time).do(scrape_books, True)
    while True:
        schedule.run_pending()
        time.sleep(sleeping_time)


if __name__ == '__main__':
    scrape_books(is_save=True)