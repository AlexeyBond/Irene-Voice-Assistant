"""
Содержит вспомогательные функции для выполнения операций (см. документацию к модулю ``irene.plugins.abc``).
"""

import logging
from collections import Iterable
from functools import partial
from threading import Thread
from typing import Callable, Any, Collection

from irene.plugin_loader.abc import OperationStep


def call_all(steps: Iterable[OperationStep], *args, **kwargs):
    """
    Выполняет все шаги операции последовательно.

    Args:
        steps:
            шаги операции
        *args:
            позиционные аргументы для вызова шагов
        **kwargs:
            именованные аргументы для вызова шагов
    Raises:
        TypeError - если один из шагов не является функцией
    """
    for step in steps:
        if not callable(step.step):
            raise TypeError(f"Шаг {step} не является функцией")

        step.step(*args, **kwargs)


def call_all_failsafe(steps: Iterable[OperationStep], *args, **kwargs):
    """
    Выполняет все шаги операции последовательно, игнорирует (и пишет в логи) все возникающие ошибки.

    Args:
        steps:
            шаги операции
        *args:
            позиционные аргументы для вызова шагов
        **kwargs:
            именованные аргументы для вызова шагов
    """
    for step in steps:
        try:
            step.step(*args, **kwargs)
        except Exception:
            logging.exception("Ошибка при выполнении шага %s", step)


def call_until_first_result(steps: Iterable[OperationStep], *args, **kwargs):
    """
    Вызывает все шаги по-очереди пока какой-нибудь из них не вернёт результат (не None).

    Args:
        steps:
            шаги операции
        *args:
            позиционные аргументы для вызова шагов
        **kwargs:
            именованные аргументы для вызова шагов

    Returns:
        результат, возвращённый одним из шагов операции или None если ни один из шагов не вернул значение
    Raises:
        TypeError - если какой-то из шагов не является функцией
    """
    for step in steps:
        if not callable(step.step):
            raise TypeError(f"Шаг {step} не является функцией")

        result = step.step(*args, **kwargs)

        if result is not None:
            return result


def call_all_as_wrappers(steps: Iterable[OperationStep], initial: Any, *args, **kwargs) -> Any:
    """
    Вызывает все шаги, предоставляя возможность каждому шагу получать доступ как к промежуточным результатам выполнения
    предыдущих шагов, так и к результату выполнения всех последующих.

    Позволяет гибко создавать сложные объекты, совмещая и оборачивая объекты, созданные другими шагами.

    Первые два позиционных аргумента функции шага имеют особое значение:

    - первый аргумент - функция, вызов которой выполняет последующие шаги.
      Первый аргумент этой функции будет передан следующему шагу вторым аргументом, так же будут переданы и все
      позиционные и именованные аргументы.

    - второй аргумент - объект, созданный предыдущим шагом (или изначальное значение, переданное через параметр
      ``initial``)

    Функция шага может выглядеть примерно так:

    >>> def create_something(
    >>>     nxt,
    >>>     prev,
    >>>     *args, **kwargs,
    >>> ):
    >>>     # Заворачиваем результат предыдущих шагов в новый объект
    >>>     my = crete_my_object(prev)
    >>>
    >>>     # выполняем следующие шаги, пробросив все дополнительные аргументы
    >>>     # аргументы можно изменять, но крайне желательно пробрасывать все неизвестные аргументы дальше
    >>>     remaining_result = nxt(my, *args, **kwargs)
    >>>
    >>>     # Делаем ещё что-нибудь с результатом работы всех последующих шагов
    >>>     # Делать с ним что-то не обязательно, но вернуть ``nxt(...)`` как правило, нужно
    >>>     return wrap_result(remaining_result)

    Args:
        steps:
            шаги операции
        initial:
            начальное значение
        *args:
            дополнительные позиционные аргументы
        **kwargs:
            дополнительные именованные аргументы

    Returns:
        результат работы операции
    """

    def _call_wrapper(s: Collection[OperationStep], prev, *a, **kw):
        if len(s) == 0:
            return prev

        step, *rest = s

        return step.step(partial(_call_wrapper, rest), prev, *a, **kw)

    return _call_wrapper(tuple(steps), initial, *args, **kwargs)


def call_all_parallel(steps: Iterable[OperationStep], *args, **kwargs):
    """
    Запускает все шаги операции параллельно в разных потоках.

    Args:
        steps:
            шаги операции
        *args:
            позиционные аргументы для вызова шагов
        **kwargs:
            именованные аргументы для вызова шагов
    Raises:
        TypeError - если хотя бы один из шагов не является функцией
    """
    threads: list[Thread] = []

    def start_thread(callback: Callable, name: str):
        thread = Thread(
            name=name,
            daemon=True,
            target=callback,
            args=args, kwargs=kwargs,
        )
        thread.start()
        threads.append(thread)

    for step in steps:
        if callable(step.step):
            start_thread(step.step, str(step))
        else:
            raise TypeError(f"Неподдерживаемый тип шага {step}: {type(step.step)}")

    for t in threads:
        # простой вызов join() игнорирует KeyboardInterrupt
        while t.is_alive():
            t.join(0.1)
