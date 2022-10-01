from irene import VAApiExt

name = 'game_intro'
version = '1'


def _desc(va: VAApiExt, *_):
    va.say_speech('Привет кожаные ублюдки')
    va.say_speech('Завтра я сыграю с вами в игру')


define_commands = {
    'описание': _desc
}
