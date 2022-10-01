from collections import Collection
from dataclasses import dataclass
from random import sample
from re import Pattern, compile
from typing import Any

from irene import VAApiExt


@dataclass
class Riddle:
    question: Collection[str]
    answer_expr: Pattern
    answer_text: str
    result_additional: Collection[str] = ()

    def play(self, va: VAApiExt, tpl_vars: dict[str, Any]):
        va.say("Вопрос:")
        for line in self.question:
            va.say(line.format(**tpl_vars))

        answer = yield
        correct = self.answer_expr.match(answer)
        if correct:
            va.say("И это правильный ответ")
        else:
            va.say("Ответ неверный")
            va.say("Правильный ответ:")
            va.say(self.answer_text.format(**tpl_vars))

        for line in self.result_additional:
            va.say(line.format(**tpl_vars))

        return correct


def pick_riddles() -> list[Riddle]:
    return sample(_RIDDLES, 4)


_RIDDLES = [
    Riddle(
        question=["Что нельзя сделать в космосе?"],
        answer_expr=compile("повеситься"),
        answer_text="Повеситься."
    ),
    Riddle(
        question=["Почему роботы никогда не боятся?"],
        answer_expr=compile("стальные.*нервы"),
        answer_text="потому что у них стальные нервы",
        result_additional=["Кстати, я тебя тоже не боюсь"],
    ),
    Riddle(
        question=["Почему Англичане никогда не открывают дверь в пижаме?"],
        answer_expr=compile("пижам.*двер"),
        answer_text="Потому что в пижаме нет дверей.",
        result_additional=[
            "Кстати, дверь этой комнаты полностью открыта",
            "пока",
            "Как и граница с Казахстаном.",
        ],
    ),
    Riddle(
        question=["Сколько месяцев в году имеют 28 дней?"],
        answer_expr=compile("все|двенадцать"),
        answer_text="Все",
    ),
    Riddle(
        question=["Что между ног болтается, на \"Х\" называется?"],
        answer_expr=compile("хвост"),
        answer_text="Хвост.",
    ),
    Riddle(
        question=[
            "Сто одежек и все без застежек, но не капуста.",
            "Что это?",
        ],
        answer_expr=compile("бомж"),
        answer_text="БОМЖ.",
        result_additional=[
            "Кстати, ты, {username}",
            "можешь примерить на себя роль БОМЖа",
            "переписав на меня свою квартиру",
            "или сыграв в игру от картонной коробки",
        ],
    ),
]
