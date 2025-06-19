"""
Автор: Wint (@Nrz315)
Плагин добавляет поддержку TTS Silero V4.
"""

import logging
from functools import cache
from typing import Optional, Any, TypedDict

import torch
import torchaudio

import irene.utils.all_num_to_text as all_num_to_text
from irene.face.abc import FileWritingTTS, TTSResultFile
from irene.face.tts_helpers import create_disposable_tts_result_file
from irene.plugin_loader.utils.snapshot_hash import snapshot_hash
from irene.utils.metadata import MetadataMapping

name = 'plugin_tts_silero_v4'
version = '0.1.0'

_logger = logging.getLogger(name)


class _Config(TypedDict):
    threads: int
    model_storage_path: str
    model_search_paths: list[str]


config: _Config = {
    "threads": 4,
    "model_storage_path": "{irene_home}/silero_v4/models/{file_name}",
    "model_search_paths": ["{irene_home}/silero_v4/models/{file_name}"],
}

config_comment = """
Настройки адаптера TTS Silero V4.

Параметры:
- `threads`: Количество потоков для синтеза
- `model_storage_path`: Путь для сохранения моделей
- `model_search_paths`: Пути для поиска моделей
"""


def _get_device() -> torch.device:
    device = torch.device('cpu')
    torch.set_num_threads(config['threads'])
    return device


@cache
def _load_model(model_url: str) -> Any:
    """Загружает модель Silero V4 с использованием официального метода"""
    try:
        # Используем torch.hub для правильной загрузки модели
        device = _get_device()
        _logger.info("Загрузка модели Silero V4 из репозитория...")

        # Загружаем модель - функция возвращает кортеж (model, symbols, sample_rate, speaker)
        hub_result = torch.hub.load(
            repo_or_dir='snakers4/silero-models',
            model='silero_tts',
            language='ru',
            speaker='v4_ru'
        )

        # Извлекаем модель из кортежа (первый элемент)
        model = hub_result[0]
        model.to(device)

        _logger.info("Модель Silero V4 успешно загружена")
        return model
    except Exception as e:
        _logger.exception(f"Ошибка загрузки модели: {e}")
        raise


def _warmup_model(model, voice_settings: dict[str, Any]):
    warmup_iterations = int(voice_settings.get('warmup_iterations', 0))
    if warmup_iterations > 0:
        warmup_phrase = voice_settings.get('warmup_phrase')
        if not warmup_phrase:
            _logger.warning("Включен разогрев, но не указана фраза")
            return

        _logger.info("Начинаю разогрев модели")
        for _ in range(warmup_iterations):
            model.apply_tts(
                texts=[warmup_phrase],
                **(voice_settings.get('silero_settings', {}) or {})
            )
        _logger.info("Разогрев завершен")


def _make_tts(instance_config: dict[str, Any]) -> Optional[FileWritingTTS]:
    model_url = instance_config.get('model_url', '')
    full_settings = instance_config.get('silero_settings', {})

    # Убедимся, что обязательные параметры установлены
    full_settings.setdefault('speaker', 'random')
    full_settings.setdefault('sample_rate', 24000)

    try:
        model = _load_model(model_url)
        _warmup_model(model, full_settings)
    except Exception as e:
        _logger.error(f"Не удалось инициализировать модель: {e}")
        return None

    all_num_to_text.load_language('ru-RU')

    class SileroV4TTS(FileWritingTTS):
        def say_to_file(self, text: str, file_base_path: Optional[str] = None, **kwargs) -> TTSResultFile:
            file = create_disposable_tts_result_file(file_base_path, '.wav')
            text = all_num_to_text.all_num_to_text(text)
            _logger.debug(f"Синтез: {text[:50]}...")

            try:
                # Генерируем аудио
                audio = model.apply_tts(
                    text=text,
                    **full_settings
                )

                # Сохраняем в формате WAV
                torchaudio.save(
                    uri=file.get_full_path(),
                    src=audio.unsqueeze(0),
                    sample_rate=full_settings["sample_rate"]
                )
            except Exception as e:
                _logger.error(f"Ошибка синтеза: {e}")
                raise

            return file

        def get_settings_hash(self) -> str:
            return str(snapshot_hash(full_settings) ^ snapshot_hash(model_url))

        @property
        def meta(self) -> MetadataMapping:
            return {
                'silero.speaker': full_settings.get('speaker'),
                'silero.sample_rate': full_settings.get('sample_rate'),
                **instance_config.get('metadata', {}),
            }

    return SileroV4TTS()


def create_file_tts(nxt, prev: Optional[FileWritingTTS], config: dict[str, Any], *args, **kwargs):
    if config.get('type') == 'silero_v4':
        prev = prev or _make_tts(config)
    return nxt(prev, config, *args, **kwargs)
