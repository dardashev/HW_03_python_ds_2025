import sys
import os

_parent_directory = os.path.dirname(os.path.abspath(__file__)) + '/..'
sys.path.append(_parent_directory)

import pytest
from unittest.mock import patch
from scraper import get_book_data, scrape_books, _get_pages_count
import json

def _get_file_path() -> str:
    file_name =  '/books_data.txt'
    return _parent_directory + '/' + file_name

def _first_book_data() -> dict[str, str|int|float|dict[str, str]]:
    return {
        'title': 'A Light in the Attic',
        'price': 51.77,
        'rating': 3,
        'available': 22,
        'description': "It's hard to imagine a world without A Light in the Attic. This now-classic collection of poetry and drawings from Shel Silverstein celebrates its 20th anniversary with this special edition. Silverstein's humorous and creative verse can amuse the dowdiest of readers. Lemon-faced adults and fidgety kids sit still and read these rhythmic words and laugh and smile and love th It's hard to imagine a world without A Light in the Attic. This now-classic collection of poetry and drawings from Shel Silverstein celebrates its 20th anniversary with this special edition. Silverstein's humorous and creative verse can amuse the dowdiest of readers. Lemon-faced adults and fidgety kids sit still and read these rhythmic words and laugh and smile and love that Silverstein. Need proof of his genius? RockabyeRockabye baby, in the treetopDon't you know a treetopIs no safe place to rock?And who put you up there,And your cradle, too?Baby, I think someone down here'sGot it in for you. Shel, you never sounded so good. ...more",
        'additional_info': {
            'UPC': 'a897fe39b1053632',
            'Product Type': 'Books',
            'Price (excl. tax)': '£51.77',
            'Price (incl. tax)': '£51.77',
            'Tax': '£0.00',
            'Availability': 'In stock (22 available)',
            'Number of reviews': '0'}
        }


def test_get_book_data():
    """
    Тестирует функцию get_book_data на корректность извлечения данных о книге.
    
    Process:
        - Парсит первую книгу
        - Сравнивает полученный словарь с ожидаемыми данными
        - Выводит подробную ошибку при несоответствии данных
    """
    url = 'http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html'
    expected_data = _first_book_data()
    result = get_book_data(url)
    
    assert result == expected_data, f'Результат не соответствует ожидаемому!\n получили:{result}\n ожидаем:{expected_data}' 


def test_scrape_books(mocker):
    
    expected_book_number = 20

    # Вернем одну первую страницу
    mocker.patch(
        'scraper._get_pages_count',
        return_value=1
    )
    result = scrape_books()

    assert len(result) == expected_book_number, f'Результат не соответствует ожидаемому!\n получили:{result} книг\n ожидаем: {expected_book_number} книг'    


def test_scrape_books_with_save_file(mocker):

    # Вернем одну первую страницу
    mocker.patch(
        'scraper._get_pages_count',
        return_value=1
    )

    # Удалим существующий файл
    file_path = _get_file_path()

    if os.path.exists(file_path):
        os.remove(file_path)

    # Запустим скрапинг в режиме сохранения в файл
    print(len(scrape_books(is_save=True)))

    result = os.path.exists(file_path)        

    assert result, f'Не найден сохраненный файл с данными парсинга books_data.txt'


def test_check_file_data():

    file_path = _get_file_path()

    if not os.path.exists(file_path):
        assert False, 'Нет файла ' + file_path

    with open(file_path, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)

    expected_data = _first_book_data()

    result = None

    for book_data in saved_data:
        if book_data['title'] == expected_data['title']:
            result = book_data
            break

    if not result:
        assert False, f'Не найдены данные книги {expected_data["title"]}'

    assert result == expected_data, f'Результат не соответствует ожидаемому!\n получили:{result}\n ожидаем:{expected_data}'

def test_remove_test_data() -> None:
    """
    Удаляет тестовые данные
    """
    file_path = _get_file_path()
    if os.path.exists(file_path):
        os.remove(file_path)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])

