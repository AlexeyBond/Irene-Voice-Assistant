from functools import partial
from inspect import isgenerator, isclass
from logging import getLogger
from typing import Optional, Callable, Any, TypeVar, Collection, SupportsFloat

from irene.brain.abc import VAContext, VAApi, VAContextSource, VAContextGenerator, VAApiExt, OutputChannelPool, \
    InboundMessage, VAContextConstructor
from irene.brain.command_tree import VACommandTree, NoCommandMatchesException, AmbiguousCommandException
from irene.brain.inbound_messages import PartialTextMessage

T = TypeVar('T')


class ApiExtProvider:
    """
    Предоставляет расширенный API (``VAApiExt``) для функций, реализующих сценарии диалогов без реализации собственного
    типа контекста, а так же предоставляет контекстам, оборачивающим такие функции информацию о дополнительных данных,
    переданных функцией.
    """

    __slots__ = ('_next_context', '_next_context_timeout', '_msg', '_construct_ctx')

    def __init__(self, context_constructor: VAContextConstructor):
        self._next_context: Optional[VAContext] = None
        self._next_context_timeout: Optional[float] = None
        self._msg: Optional[InboundMessage] = None
        self._construct_ctx = context_constructor

    def get_next_context(self, default: Optional[VAContext]) -> Optional[VAContext]:
        """
        Возвращает следующий контекст, которому должно быть передано управление.

        Если функция вызывала метод context_set, то вернёт контекст, переданный в этот метод, добавив таймаут, если был
        передан соответствующий дополнительный параметр.

        Args:
            default:
                контекст, который следует вернуть если функция не вызывала context_set

        Returns:
            контекст, которому нужно передать управление далее, None если диалог завершён
        """
        try:
            next_ctx = default

            if self._next_context is not None:
                next_ctx = self._next_context

            if next_ctx is None:
                return None

            if self._next_context_timeout is None:
                return next_ctx
            else:
                return TimeoutOverrideContext(next_ctx, self._next_context_timeout)
        finally:
            self._next_context = None
            self._next_context_timeout = None

    def get_next_context_from_returned_value(
            self,
            returned: Any,
            va: VAApi,
            default: Optional[VAContext] = None
    ) -> Optional[VAContext]:
        """
        Возвращает контекст, которому следует передать управление с учётом значения, возвращённого функцией диалога.

        Args:
            returned:
                значение, возвращённое функцией диалога
            va:
            default:
                контекст, который следует вернуть если функция не вернула значения из которого можно создать
                контекст и не вызывала context_set

        Returns:
            контекст, которому следует передать управление
        """
        if isgenerator(returned):
            ctx = GeneratorContext(returned, self).start(va)
        else:
            ctx = self.get_next_context(default)

        if ctx is not None:
            ctx = self._construct_ctx(ctx)

        return ctx

    def set_timeout_override(self, timeout: float):
        self._next_context_timeout = timeout

    def set_inbound_message(self, msg: Optional[InboundMessage]):
        """
        Сохраняет ссылку на обрабатываемое сообщение, делая метод ``get_message`` работоспособным.
        """
        self._msg = msg

    def using_va(self, va: VAApi) -> VAApiExt:
        """
        Возвращает экземпляр расширенного API для данного экземпляра базового API.
        """
        provider = self

        class _ApiExtImpl(VAApiExt):
            __slots__ = ()

            def get_message(self) -> InboundMessage:
                msg = provider._msg

                if msg is None:
                    raise RuntimeError(
                        'get_message вызван не из обработчика команды либо API инициализирован некорректно'
                    )

                return msg

            def context_set(self, ctx: VAContextSource, timeout: Optional[float] = None):
                provider._next_context = provider._construct_ctx(ctx, ext_api_provider=provider)
                provider._next_context_timeout = timeout

            def submit_active_interaction(self, *args, **kwargs):
                if 'related_message' not in kwargs and provider._msg is not None:
                    kwargs['related_message'] = provider._msg

                return va.submit_active_interaction(*args, **kwargs)

            def get_outputs(self) -> OutputChannelPool:
                return va.get_outputs()

        return _ApiExtImpl()


def _function_to_str(fn: Callable):
    mod = getattr(fn, "__module__", r"¯\_(ツ)_/¯")
    name = getattr(fn, "__qualname__", str(fn))
    return f'{mod}.{name}'


class FunctionContext(VAContext):
    """
    Контекст, однократно вызывающий заданную функцию при получении команды.
    """
    __slots__ = ('_fn', '_ext', '_construct_ctx')

    def __init__(
            self,
            fn: Callable[[VAApiExt, str], Any],
            *,
            ext_api_provider: Optional[ApiExtProvider],
            context_constructor: VAContextConstructor,
    ):
        self._fn = fn
        self._ext = ext_api_provider
        self._construct_ctx: VAContextConstructor = context_constructor

    def handle_command(self, va: VAApi, message: InboundMessage) -> Optional[VAContext]:
        ext = self._ext or ApiExtProvider(self._construct_ctx)
        ext.set_inbound_message(message)

        return ext.get_next_context_from_returned_value(self._fn(ext.using_va(va), message.get_text()), va)

    def __str__(self):
        return _function_to_str(self._fn)


class FunctionContextWithArgs(VAContext):
    """
    Контекст, однократно вызывающий заданную функцию при получении команды и передающий
    этой функции дополнительный аргумент.
    """
    __slots__ = ('_fn', '_arg', '_ext', '_construct_ctx')

    def __init__(
            self,
            fn: Callable[[VAApiExt, str, T], None],
            arg: T,
            *,
            ext_api_provider: Optional[ApiExtProvider],
            context_constructor: VAContextConstructor,
    ):
        self._fn = fn
        self._arg = arg
        self._ext = ext_api_provider
        self._construct_ctx: VAContextConstructor = context_constructor

    def handle_command(self, va: VAApi, message: InboundMessage) -> Optional[VAContext]:
        ext = self._ext or ApiExtProvider(self._construct_ctx)

        ext.set_inbound_message(message)

        return ext.get_next_context_from_returned_value(self._fn(ext.using_va(va), message.get_text(), self._arg), va)

    def __str__(self):
        return f'{_function_to_str(self._fn)}({self._arg})'


class ContextTimeoutException(Exception):
    pass


class GeneratorContext(VAContext):
    """
    Контекст, поведение которого определяется генератором.
    FunctionContext и FunctionContextWithArgs создают такой контекст когда функция возвращает генератор.

    Новые полученные команды отправляются генератору через метод send(), значения, сгенерированные генератором
    воспринимаются как реплики ассистента.

    def play_game(va: VAApi, phrase: str) -> VAContextGenerator:
        # yield со значением - произносит фразу и ожидает ответа
        phrase = yield "Скажи правила или начать"

        while True:
            match phrase:
                case "отмена":
                    # return со значением завершает диалог
                    return "Поняла, играть не будем"
                case "правила":
                    phrase = yield "Правила игры. Я загадываю число ... бла бла бла"
                case "начать" | "повторить":
                    try:
                        ...
                    except ContextTimeoutException:
                        # yield кидает ContextTimeoutException когда пользователь не отвечает слишком долго
                        phrase = yield "Ты слишком долго думал." \
                            "Засчитываю техническое поражение. Скажи повторить чтобы начать снова."
                case _:
                    phrase = yield "Не поняла..."
    """
    __slots__ = ('_gen', '_ext')

    def __init__(self, generator: VAContextGenerator, ext: ApiExtProvider):
        self._gen = generator
        self._ext = ext

    def _process_result(self, va: VAApi, value: Any, default_next_ctx: Optional[VAContext]) -> Optional[VAContext]:
        """
        Обрабатывает значение, yield'нутое или возвращённое генератором.

        Args:
            va:
            value: значение yield'нутое или возвращённое генератором
            default_next_ctx: контекст продолжения диалога для случаев когда значение, полученное от генератора не
            требует смены контекста

        Returns: контекст для продолжения диалога или None для завершения диалога
        """
        if isinstance(value, str):
            self._ext.using_va(va).say(value)
        elif isinstance(value, tuple):
            if len(value) >= 1:
                first, *rest = value

                if isinstance(first, str):
                    self._ext.using_va(va).say(first)

                if len(rest) >= 1:
                    if isinstance(rest[0], SupportsFloat):
                        self._ext.set_timeout_override(float(rest[0]))

        return self._ext.get_next_context_from_returned_value(
            value,
            va,
            default_next_ctx
        )

    def start(self, va: VAApi) -> Optional[VAContext]:
        try:
            val = next(self._gen)
        except StopIteration as e:
            return self._process_result(va, e.value, None)

        return self._process_result(va, val, self)

    def handle_command(self, va: VAApi, message: InboundMessage) -> Optional[VAContext]:
        try:
            self._ext.set_inbound_message(message)
            val = self._gen.send(message.get_text())
        except StopIteration as e:
            return self._process_result(va, e.value, None)

        return self._process_result(va, val, self)

    def handle_timeout(self, va: VAApi) -> Optional[VAContext]:
        try:
            val = self._gen.throw(ContextTimeoutException())
        except StopIteration as e:
            return self._process_result(va, e.value, None)
        except ContextTimeoutException:
            # Генератор не перехватил ContextTimeoutException - завершаем диалог
            return None

        return self._process_result(va, val, self)


class CommandTreeContext(VAContext):
    """
    Контекст, интерпретирующий команды с помощью дерева команд (VACommandTree).
    """
    __slots__ = ('_tree', '_unknown_command_context', '_ambiguous_command_context')

    logger = getLogger('CommandTreeContext')

    def __init__(
            self,
            tree: VACommandTree,
            unknown_command_context: Optional[VAContext] = None,
            ambiguous_command_context: Optional[VAContext] = None,
    ):
        """
        Args:
            tree: дерево команд
            unknown_command_context: контекст, которому будут переданы нераспознанные команды
            ambiguous_command_context: контекст, которому будут переданы неоднозначно распознанные команды.
                По-умолчанию, будет использоваться unknown_command_context.
        """
        self._tree = tree
        self._unknown_command_context = unknown_command_context
        self._ambiguous_command_context = ambiguous_command_context or unknown_command_context

    def _handle_error(self, va: VAApi, message: InboundMessage, handler_context: Optional[VAContext]) \
            -> Optional[VAContext]:
        if handler_context:
            return handler_context.handle_command(va, message)

        return self

    def handle_command(self, va: VAApi, message: InboundMessage) -> Optional[VAContext]:
        try:
            ctx: VAContext
            ctx, rest_text = self._tree.get_command(message.get_text())
        except NoCommandMatchesException as e:
            self.logger.info(str(e))

            return self._handle_error(va, message, self._unknown_command_context)
        except AmbiguousCommandException as e:
            self.logger.info(str(e))

            return self._handle_error(va, message, self._ambiguous_command_context)

        return ctx.handle_command(va, PartialTextMessage(message, rest_text))


class TriggerPhraseContext(VAContext):
    """
    Контекст, ожидающий появления во входящем потоке ключевой фразы (имени ассистента) и передающий управление
    следующему контексту при его обнаружении.
    """
    __slots__ = ('_phrases', '_next_context')

    def __init__(self, phrases: Collection[Collection[str]], next_context: VAContext):
        """
        Args:
            phrases: набор ключевых фраз. Каждая фраза представлена как коллекция слов.
            next_context: контекст, которому нужно передать управление в случае обнаружения ключевой фразы.
                Остаток фразы будет передан в метод handle_command этого контекста.
        """
        self._phrases = phrases
        self._next_context = next_context

    def handle_command(self, va: VAApi, message: InboundMessage) -> Optional[VAContext]:
        words = message.get_text().split(' ')

        while len(words) > 0:
            for phrase in self._phrases:
                if words[:len(phrase)] == phrase:
                    rest_text = ' '.join(words[len(phrase):])

                    return self._next_context.handle_command(va, PartialTextMessage(message, rest_text))

            words = words[1:]

        return None


class InterruptContext(VAContext):
    """
    Контекст, который создаётся когда текущий диалог прерывается новым диалогом "по инициативе" ассистента.

    Делегирует все операции контексту прерывающего диалога.
    Когда тот завершается - возвращается к прерванному диалогу.
    """
    __slots__ = ('_interrupted', '_current')

    def __init__(self, interrupted: VAContext, current: VAContext):
        """
        Args:
            interrupted: контекст прерванного диалога.
                         Метод handle_interrupt прерванного контекста должен быть вызван до создания InterruptContext.
            current: контекст прерывающего диалога.
        """
        self._interrupted = interrupted
        self._current = current

    def _process_next_ctx(self, va: VAApi, ctx: Optional[VAContext]) -> Optional[VAContext]:
        if ctx is None:
            return self._interrupted.handle_restore(va)

        self._current = ctx
        return self

    def handle_command(self, va: VAApi, message: InboundMessage) -> Optional[VAContext]:
        return self._process_next_ctx(va, self._current.handle_command(va, message))

    def handle_timeout(self, va: VAApi) -> Optional[VAContext]:
        return self._process_next_ctx(va, self._current.handle_timeout(va))

    def get_timeout(self, default: float) -> float:
        return self._current.get_timeout(default)

    def handle_interrupt(self, va: VAApi) -> Optional[VAContext]:
        return self._process_next_ctx(va, self._current.handle_interrupt(va))

    def handle_restore(self, va: VAApi) -> Optional[VAContext]:
        return self._process_next_ctx(va, self._current.handle_restore(va))


class BaseContextWrapper(VAContext):
    """
    Базовый класс для обёрток над контекстом.
    """
    __slots__ = '_wrapped'

    def __init__(self, wrapped: VAContext):
        self._wrapped = wrapped

    def _wrap_next(self, ctx: Optional[VAContext]) -> Optional[VAContext]:
        if ctx is self._wrapped:
            return self

        return ctx

    def handle_command(self, va: VAApi, message: InboundMessage) -> Optional[VAContext]:
        return self._wrap_next(self._wrapped.handle_command(va, message))

    def handle_timeout(self, va: VAApi) -> Optional[VAContext]:
        return self._wrap_next(self._wrapped.handle_timeout(va))

    def handle_interrupt(self, va: VAApi) -> Optional[VAContext]:
        return self._wrap_next(self._wrapped.handle_interrupt(va))

    def handle_restore(self, va: VAApi) -> Optional[VAContext]:
        return self._wrap_next(self._wrapped.handle_restore(va))

    def get_timeout(self, default: float) -> float:
        return self._wrapped.get_timeout(default)


class TimeoutOverrideContext(BaseContextWrapper):
    """
    Обёртка для контекста, добавляющая нестандартный таймаут (интервал ожидания следующей команды).
    """
    __slots__ = '_timeout'

    def __init__(self, wrapped: VAContext, timeout: float):
        super().__init__(wrapped)
        self._timeout = timeout

    def get_timeout(self, default: float) -> float:
        return self._timeout


UNKNOWN_COMMAND_SPECIAL_KEY = '[unknown]'
AMBIGUOUS_COMMAND_SPECIAL_KEY = '[ambiguous]'


def construct_context(
        src: VAContextSource,
        *,
        ext_api_provider: Optional[ApiExtProvider] = None,
        construct_nested: Optional[VAContextConstructor] = None,
        **_kwargs,
) -> VAContext:
    """
    Создаёт контекст диалога из исходного объекта:

    - из класса, являющегося подклассом ``VAContext`` создаёт его экземпляр, вызывая конструктор без дополнительных
      аргументов

    - из функции - контекст, вызывающий эту функцию (см. ``FunctionContext``)

    - из кортежа с функцией и параметром - контекст, вызывающий эту функцию с этим параметром
      (см. ``FunctionContextWithArgs``)

    - из словаря со строковыми ключами - строит дерево команд (см. ``VACommandTree``) и создаёт на его основе контекст
      (см. ``CommandTreeContext``).
      Ключи ``"[unknown]"`` (``UNKNOWN_COMMAND_SPECIAL_KEY``) и ``"[ambiguous]"`` (``AMBIGUOUS_COMMAND_SPECIAL_KEY``)
      переданного словаря используются для создания контекстов, обрабатывающих нераспознанные и неоднозначно
      распознанные команды соответственно.

    - если переданный объект уже является контекстом - то он возвращается без изменений

    Эта функция является реализацией ``VAContextConstructor`` по-умолчанию.

    Args:
        src:
            исходный объект - функция, кортеж из функции и аргумента, словарь или уже готовый контекст
        ext_api_provider:
            экземпляр ``ApiExtProvider`` для случаев, когда контекст создаётся через ``VAApiExt.context_set``.
            Если исходный объект является функцией, то созданный контекст будет переиспользовать существующий
            ``ApiExtProvider``, тем самым сохраняя некоторые настройки, установленные предыдущей функцией.
        construct_nested:
            Функция, которая будет использоваться для создания дополнительных контекстов - контекстов команд в случае
            получения словаря, контекстов, порождаемых создаваемым контекстом.
            Если аргумент не передан, то будет использоваться сама функция ``construct_context``.

    Returns:
        готовый контекст
    Raises:
        ValueError
        TypeError
    """
    if construct_nested is None:
        construct_nested = partial(construct_context, ext_api_provider=ext_api_provider)

    if isinstance(src, VAContext):
        return src

    if isclass(src) and issubclass(src, VAContext):
        return src()

    if callable(src):
        return FunctionContext(src, ext_api_provider=ext_api_provider, context_constructor=construct_nested)

    if isinstance(src, dict):
        src = src.copy()
        unknown_command_context, = src.pop(UNKNOWN_COMMAND_SPECIAL_KEY, None),
        ambiguous_command_context, = src.pop(AMBIGUOUS_COMMAND_SPECIAL_KEY, None),

        tree = VACommandTree[VAContext]()
        tree.add_commands(src, construct_nested)
        uc_constructed, ac_constructed = None, None

        if unknown_command_context is not None:
            uc_constructed = construct_nested(unknown_command_context)

        if ambiguous_command_context is not None:
            if ambiguous_command_context is unknown_command_context:
                ac_constructed = uc_constructed
            else:
                ac_constructed = construct_nested(ambiguous_command_context)

        return CommandTreeContext(tree, uc_constructed, ac_constructed)

    if isinstance(src, tuple):
        if len(src) == 2:
            first, second = src

            if callable(first):
                fn: Callable = first
                return FunctionContextWithArgs(
                    fn,
                    second,
                    ext_api_provider=ext_api_provider,
                    context_constructor=construct_nested
                )
            else:
                raise ValueError(
                    "Первое значение в кортеже для создания контекста должно быть функцией. "
                    f"Вместо этого передан кортеж с {repr(src)} в первом элементе"
                )
        else:
            raise ValueError(
                "Кортеж для создания контекста должен содержать ровно два значения - функцию и аргумент. "
                f"Вместо этого передан кортеж {repr(src)}"
            )

    raise TypeError(f'Попытка создать контекст из объекта неподдерживаемого типа ({type(src)}): {repr(src)}')
