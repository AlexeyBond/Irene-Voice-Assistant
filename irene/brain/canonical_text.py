import re

"""
Модуль для работы с текстом в каноничном формате.

Текст является каноничным если:
- все буквы приведены к нижнему регистру
- между словами ровно один пробел
- пробелы в начале и в конце строки отсутствуют
- в тексте не содержится иных пробельных символов кроме пробела
- в тексте не содержится символов пунктуации
"""


def convert_to_canonical(text: str) -> str:
    """
    Преобразует текст к каноничному виду.

    Args:
        text:
            текст сообщения
    Returns:
        текст сообщения в каноничном формате
    """
    return re.sub(r'[\W_]+', ' ', text).strip().lower()


def is_canonical(text: str) -> bool:
    """
    Проверяет, имеет ли данный текст каноничный формат.

    Args:
        text:
            текст для проверки

    Returns:
        True если и только если текст имеет канонический формат
    """
    return re.fullmatch(r'(?:(?:\w+ )*\w+)?', text) is not None and text.lower() == text
