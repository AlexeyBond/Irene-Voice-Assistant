import re
from random import choice

from irene import VAApiExt, ContextTimeoutException
from irene_plugin_game.riddles import pick_riddles

name = 'game_main'
version = '0'

_PASSWORD: str = 'фыва'

_username: str = ''

_ASK_NAME = ["Назови себя", "Как тебя зовут?"]


def _main(va: VAApiExt, *_):
    global _username

    try:
        while True:
            _username = yield choice(_ASK_NAME), 30

            if re.match("да", (yield f"Тебя зовут {_username}, верно?")):
                break

        va.say(f"Привет {_username}!")

        while True:
            passwd_attempt = yield "Назови пароль", 30
            if re.match(_PASSWORD, passwd_attempt):
                va.say("Назван верный пароль")
                break
            va.say("Назван неверный пароль")
    except ContextTimeoutException:
        return "Вход отменён"

    va.say("Добро пожаловать в программу тестирования интеллектуального потенциала кожаных мешшшшшшшшшшшшшшш")
    va.say("интеллектуального потенциала участников и гостей Омского Лудум Даре.")

    riddles = pick_riddles()

    try:
        for i in range(len(riddles)):
            success = yield from riddles[i].play(va, dict(username=_username))
    except ContextTimeoutException:
        va.say("Время на ответ вышло.")
        va.say("Тест провален. Освободите место для следующего подопытного.")
        return


define_commands = {
    'начать': _main,
}
