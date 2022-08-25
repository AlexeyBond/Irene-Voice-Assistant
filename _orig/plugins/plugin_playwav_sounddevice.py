# Playwav plugin for sounddevice engine
# author: Vladislav Janvarev

import os

import sounddevice as sound_device
import soundfile as sound_file

from _orig.vacore import VACore

modname = os.path.basename(__file__)[:-3] # calculating modname

# функция на старте
def start(core:VACore):
    manifest = {
        "name": "PlayWav through sounddevice",
        "version": "1.0",
        "require_online": False,

        "playwav": {
            "sounddevice": (init,playwav) # первая функция инициализации, вторая - проиграть wav-файл
        }
    }
    return manifest

def start_with_options(core:VACore, manifest:dict):
    pass

def init(core:VACore):
    pass

def playwav(core:VACore, wavfile:str):
    #AudioPlayer(wavfile).play(block=True)
    filename = os.path.dirname(__file__)+"/../"+wavfile

    #filename = 'timer/Sounds/Loud beep.wav'
    # now, Extract the data and sampling rate from file
    data_set, fsample = sound_file.read(filename, dtype = 'float32')
    sound_device.play(data_set, fsample)
    # Wait until file is done playing
    status = sound_device.wait()
    return

