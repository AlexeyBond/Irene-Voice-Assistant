# Работа в клиент-серверном режиме

Данный документ содержит информацию о низкоуровневых деталях взаимодействия клиента и сервера ассистента и предназначен
в первую очередь для разработчиков изучающих работу соответствующего кода, а так же разрабатывающих собственные клиенты
и расширения для сервера. Для получения инструкций по настройке клиент-серверного режима для обычных пользователей
обратитесь к *[ДОКУМЕНТ НЕ СОЗДАН]*.

## Общая информация

Клиент и сервер соединяются по протоколу WebSocket и взаимодействуют обмениваясь текстовыми сообщениями. Каждое
сообщение представляет собой JSON-объект, с одним обязательным полем ``type``, определяющим тип сообщения и набором
дополнительных полей, зависящих от типа сообщения.

Для подключения к web-сокету клиент должен использовать путь `/api/face_web/ws`.

Клиент и сервер могут одновременно с основным соединением по WebSocket устанавливать дополнительные соединения в т.ч.
дополнительные WebSocket-соединения.

## Согласование протоколов

Связь между клиентом и сервером решает две основные задачи - передачу команд от клиента к серверу и передачу ответов от
сервера к клиенту. Конкретные способы передачи команд и ответов зависят от используемых соединением протоколов.
Различные клиенты и различные конфигурации сервера могут поддерживать разные наборы протоколов. Для выбора используемых
протоколов при установке соединения осуществляется согласование протоколов.

При подключении клиент отправляет список необходимых ему протоколов в поле ``"protocols"`` сообщения
типа ``"negotiate/request"``. Каждый элемент списка представляет собой список, содержащий названия протоколов, хотя бы
один из которых необходим клиенту для работы. Сервер выбирает из каждого элемента списка первый поддерживаемый протокол
и возвращает список выбранных протоколов в поле ``"protocols"`` сообщения типа ``"negotiate/agree"``.

Пример:

Клиенту требуется поддержка хотя бы одного из протоколов ``in.text-direct`` и ``in.text-indirect``, а так же хотя бы
одного из протоколов ``out.tts-serverside-file-link`` и ``out.text-plain``. После подключения клиент отправляет
следующее сообщение:

```yaml
{
  "type": "negotiate/request",
  "protocols": [
    [ "in.text-direct", "in.text-indirect" ],
    [ "out.tts.serverside", "out.text-plain" ]
  ]
}
```

Допустим, сервер поддерживает протоколы ``in.text-indirect``, ``out.tts-serverside-file-link``, ``out.text-plain``,
тогда он выбирает первый поддерживаемый протокол из каждого элемента списка, полученного от клиента и отвечает следующим
сообщением:

```yaml
{
  "type": "negotiate/agree",
  "protocols": [ "in.text-indirect", "out.tts.serverside" ]
}
```

Заметьте, что протокол ``out.text-plain`` не возвращается и сервер не обязан поддерживать его в рамках данного
соединения.

# Протоколы

Далее приведён список протоколов, поддержка которых реализована в коде, хранящемся в основном репозитории.

## Непрямой текстовый ввод (``in.text-indirect``)

Позволяет клиенту отправлять текстовые сообщения ассистенту. При этом, сообщения по-умолчанию не трактуются как
адресованные ассистенту. Чтобы ассистент среагировал на сообщение, в нём должно содержаться его имя (как правило,
указанное в конфиге плагина
``brain``).

Для отправки сообщения клиент должен отправить следующее сообщение:

```yaml
{
  "type": "in.text-indirect/text",
  "text": "<текст сообщения>",
}
```

Может использоваться, например, для отправки результатов распознания речи, осуществлённого на клиенте или для
прослушивания группового чата в мессенджере.

## Ввод речи, распознанной на клиенте (``in.stt.clientside``)

Аналогичен протоколу ``in.text-indirect``, но клиенту отправляется ответное сообщение если распознанный текст
(или его часть) были восприняты как текст адресованный ассистенту.

Клиент отправляет распознанный текст в сообщении следующего вида:

```yaml
{
  "type": "in.stt.clientside/recognized",
  "text": "<распознанный текст>",
}
```

Сервер *может* ответить сообщением следующего вида:

```yaml
{
  "type": "in.stt.clientside/processed",
  "text": "<использованная часть распознанного текста>",
}
```

Например, между клиентом и сервером может состояться следующий обмен сообщениями:

```yaml
{ # Клиент серверу
  "type": "in.stt.clientside/recognized",
  "text": "бла бла блаб бла",
}
# ответа нет
---
{ # Клиент серверу
  "type": "in.stt.clientside/recognized",
  "text": "бла бла ирина включи свет",
}
---
{ # Сервер клиенту
  "type": "in.stt.clientside/processed",
  "text": "включи свет",
}
```

Протокол предназначен для тех случаев, когда в клиентском приложении, использующем распознание речи, нужно отображать
историю сообщений, но не нужно отображать весь распознанный текст. В случаях, когда отображать историю сообщений не
нужно, достаточно использовать протокол ``in.text-indirect``.

## Прямой текстовый ввод (``in.text-direct``)

Аналогичен протоколу ``PROTOCOL_IN_TEXT_INDIRECT``, но сообщение всегда воспринимается как адресованное ассистенту.

Для отправки сообщения клиент должен отправить следующее сообщение:

```yaml
{
  "type": "in.text-direct/text",
  "text": "<текст сообщения>",
}
```

Может использоваться для отправки сообщений из прямого чата с ассистентом или при распознании речи на клиенте, когда
обнаружение имени ассистента происходит там же.

## Текстовый вывод (``out.text-plain``)

Позволяет серверу выводить ответы в виде текста.

Сервер будет отправлять сообщения такого вида:

```yaml
{
  "type": "out.text-plain/text",
  "text": "<текст сообщения>",
}
```

Может использоваться для вывода текстовых ответов в чаты.

## Вывод аудио по ссылке (out.audio.link)

Используется для воспроизведения аудио-файлов на клиенте.

При получении команды на воспроизведение файла сервер делает этот файл доступным (в текущей реализации - временно
доступным) по некоторой ссылке. Затем сервер отправляет клиенту сообщение, что необходимо воспроизвести файл,
находящийся по заданному адресу. В процессе воспроизведения и по окончание воспроизведения клиент периодически оповещает
сервер о статусе процесса.

Первое сообщение от сервера имеет следующий вид:

```yaml
{
  "type": "out.audio.link/playback-request",
  "url": "/путь/к/файлу",
  "playbackId": "<уникальный идентификатор воспроизведения>",
  "altText": "текст, описывающий воспроизводимый звук", # не обязательное поле
}
```

Поле ``"altText"`` может содержать текст сообщения в случае передачи звука, сгенерированного TTS или что-нибудь не очень
осмысленное вроде ``"ПИИИК"`` или ``"🔊"`` для не-речевых звуков, впрочем, последнее необязательно.

В процессе воспроизведения клиент каждую секунду отправляет сообщение следующего вида:

```yaml
{
  "type": "out.audio.link/playback-progress",
  "playbackId": "<уникальный идентификатор воспроизведения, из первого сообщения>",
}
```

И по окончание воспроизведения:

```yaml
{
  "type": "out.audio.link/playback-done",
  "playbackId": "<уникальный идентификатор воспроизведения, из первого сообщения>",
}
```

Последние два пункта необходимы для отслеживания сервером момента окончания воспроизведения без зависания при разрыве
соединения и с теоретической (не реализовано на клиентской стороне на момент написания документа) возможностью
продолжения ожидания при кратковременном разрыве соединения.

## Серверный TTS (``out.tts.serverside``)

Протокол разрешает серверу использовать подходящий протокол передачи аудио данных (например, ``out.audio.link``) для
передачи речи, синтезированной TTS. Никаких дополнительных типов сообщений не добавляется.

В текущей реализации, для успешного согласования этого протокола его необходимо передавать в списке запрашиваемых
протоколов после протокола передачи аудио:

```yaml
{
  "type": "negotiate/request",
  "protocols": [ [ "out.audio.link" ], [ "out.tts.serverside" ] ]
}
```

## Заглушение микрофонов (``in.mute``)

Протокол не передаёт команды пользователя или ответы ассистента, но сообщает клиенту, когда следует выключить микрофоны.
Как правило, это нужно когда сам клиент, другой клиент рядом или сервер воспроизводят голосовой ответ ассистента, чтобы
предотвратить распознание голосового ответа как команды от пользователя.

Когда микрофон нужно выключить, сервер передаёт следующее сообщение:

```yaml
{
  "type": "in.mute/mute",
}
```

Когда микрофон можно снова включить - передаётся другое сообщение:

```yaml
{
  "type": "in.mute/unmute",
}
```

## Распознание речи на сервере (``in.stt.serverside``)

Позволяет выполнять распознание речи на сервере. Клиенту достаточно передавать аудио-поток через дополнительное
web-socket соединение.

Когда сервер готов принять соединение для передачи аудио-потока, он отправляет сообщение следующего вида:

```yaml
{
  "type": "in.stt.serverside/ready",
  "path": "<путь для Web-socket соединения>",
}
```

В поле `path` этого сообщения находится путь, который должен быть использован при создании web-socket соединения. При
подключении в web-сокету клиент может передать дополнительный параметр `sample_rate` - частоту дискретизации
отправляемых аудио-данных. По-умолчанию, частота дискретизации будет считаться равной 44100 Гц.

Например, получив при подключении к серверу ассистента, запущенному на  `http://irene.local:8086/` сообщение

```yaml
{
  "type": "in.stt.serverside/ready",
  "path": "/api/plugin_in_stt_serverside/44aec96f-8314-41fe-9f9c-494b06a23c8e",
}
```

клиент может использовать следующий URL для создания дополнительного web-socket соединения:

```
ws://irene.local:8086/api/plugin_in_stt_serverside/44aec96f-8314-41fe-9f9c-494b06a23c8e?sample_rate=88200
```

TODO: Описать выбор формата сэмплов и порядка байтов. В текущей реализации сервер ожидает 16-битные знаковые числа с
порядком байтов, определяемым ОС сервера.

Сервер будет оповещать клиента о распознанном тексте сообщениями следующего вида:

```yaml
{
  "type": "in.stt.serverside/recognized",
  "text": "<распознанный текст>",
}
```

И если этот текст (или его часть) будет интерпретирован как команда, то будет отправлено сообщение следующего вида:

```yaml
{
  "type": "in.stt.serverside/processed",
  "text": "<распознанный текст>",
}
```
