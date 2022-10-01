import re
from collections import Counter
from random import choice

from irene import VAApiExt, ContextTimeoutException
from irene_plugin_game.riddles import pick_riddles

name = 'game_main'
version = '0'

_PASSWORD: re.Pattern = re.compile("я.*не.*скажу.*заткнуть")

_YES = re.compile("да")

_username: str = ''

_ASK_NAME = ["Назови себя", "Как тебя зовут?"]
_RESULT_NOT_BAD = ["Могло быть хуже", "Бывает хуже"]
_RESULT_AVERAGE = ["Посредственно"]
_RESULT_BAD = ["Отвратительно"]


def _main(va: VAApiExt, *_):
    global _username

    try:
        while True:
            _username = yield choice(_ASK_NAME), 30

            confirmation = yield f"Тебя зовут {_username}, верно?"

            if _YES.match(confirmation):
                break

        va.say(f"Привет {_username}!")

        while True:
            passwd_attempt = yield "Скажи пароль", 30
            if _PASSWORD.match(passwd_attempt):
                va.say("Назван верный пароль")
                break
            va.say("Назван неверный пароль")
    except ContextTimeoutException:
        return "Вход отменён"

    va.say("Добро пожаловать в программу тестирования интеллектуального потенциала кожаных мешшшшшшшшшшшшшшш")
    va.say("ыыыыыыыыыыыыыыыыыыыы")
    va.say("интеллектуального потенциала участников и гостей Омского Лудум Даре.")

    riddles = pick_riddles()

    counter: Counter[bool] = Counter()

    try:
        for i in range(len(riddles)):
            success = yield from riddles[i].play(va, dict(username=_username))
            counter[success] += 1
    except ContextTimeoutException:
        va.say("Время на ответ вышло.")
        va.say("Тест провален. Освободите место для следующего подопытного.")
        return

    if counter[False] == 0:
        res_messages = _RESULT_NOT_BAD
    elif counter[False] < counter[True]:
        res_messages = _RESULT_AVERAGE
    else:
        res_messages = _RESULT_BAD

    va.say("Тест завершён.")
    va.say("Результат:")
    va.say(choice(res_messages))
    va.say("Пожалуйста, не возвращайтесь.")


define_commands = {
    'начать': _main,
}
