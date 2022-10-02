from random import choice

from irene import VAApiExt
from irene.plugin_loader.file_match import match_files

name = 'beep'
version = '1.0.0'

config = {
    'filePath': '{irene_path}/embedded_plugins/media/timer.wav',
}


def _signal(va: VAApiExt, *_):
    fp = choice(list(match_files(config['filePath'])))
    va.play_audio(fp)
    va.say('!')


define_commands = {
    "сигнал": _signal,
}
