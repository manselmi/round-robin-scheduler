# vim: set ft=python :

import itertools
import logging
import sys
from collections.abc import Callable, Sequence
from enum import IntEnum, StrEnum, auto
from types import TracebackType

import orjson
import structlog
from structlog.typing import Processor, WrappedLogger

logger = structlog.get_logger(__name__)


class Level(IntEnum):
    NOTSET = logging.NOTSET
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LevelName(StrEnum):
    NOTSET = Level.NOTSET.name
    DEBUG = Level.DEBUG.name
    INFO = Level.INFO.name
    WARNING = Level.WARNING.name
    ERROR = Level.ERROR.name
    CRITICAL = Level.CRITICAL.name


class Renderer(StrEnum):
    AUTO = auto()
    CONSOLE = auto()
    JSON = auto()


class InvalidRendererError(ValueError):
    pass


def configure_structlog(
    *,
    min_level: Level = Level.NOTSET,
    processors: Sequence[Processor] | None = None,
    renderer: Renderer = Renderer.AUTO,
) -> None:
    pre_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if processors is None:
        processors = []

    if renderer == Renderer.AUTO:
        renderer = Renderer.CONSOLE if sys.stdout.isatty() else Renderer.JSON

    logger_factory: Callable[..., WrappedLogger]
    post_processors: list[Processor]
    if renderer == Renderer.CONSOLE:
        logger_factory = structlog.PrintLoggerFactory()
        post_processors = [
            structlog.dev.ConsoleRenderer(),
        ]
    elif renderer == Renderer.JSON:
        logger_factory = structlog.BytesLoggerFactory()
        post_processors = [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(serializer=orjson.dumps),
        ]
    else:
        raise InvalidRendererError(renderer)

    structlog.configure_once(
        cache_logger_on_first_use=True,
        logger_factory=logger_factory,
        processors=list(itertools.chain(pre_processors, processors, post_processors)),
        wrapper_class=structlog.make_filtering_bound_logger(min_level),
    )

    sys.excepthook = handle_unhandled_exception


def handle_unhandled_exception(
    type_: type[BaseException],
    value: BaseException,
    traceback: TracebackType | None,
    /,
) -> None:
    if issubclass(type_, Exception):
        logger.critical("unhandled_exception", exc_info=(type_, value, traceback))
    sys.__excepthook__(type_, value, traceback)
