from __future__ import annotations


from typing import Literal, Optional, Any, Type, TypeVar
from pydantic import BaseModel
from dataclasses import dataclass, fields

from typing_extensions import TypeAlias

import numpy as np
import numpy.typing as npt

from typing import TypeVar
from dataclasses import is_dataclass

EventT = TypeVar('EventT')

_event_registry: dict[str, Type[Any]] = {}
def register_event(cls: Type[EventT]) -> Type[EventT]:
    """Class decorator to auto-register by its `type` field."""
    if not is_dataclass(cls):
        raise TypeError("register_event can only be used with dataclass types")
    # Grab the default value from the `type` field
    tfield = next(f for f in fields(cls) if f.name == "type")
    type_value = getattr(cls, "type", None) or tfield.default
    if type_value is None or type_value is dataclass._MISSING_TYPE:  # type: ignore
        raise ValueError(f"Event class {cls.__name__} must have a 'type' field with a default value or class attribute")
    if not isinstance(type_value, str):
        raise TypeError(f"'type' field value must be a string, got {type(type_value)}")
    _event_registry[type_value] = cls
    return cls

@register_event
@dataclass
class AudioEvent():
    data: npt.NDArray[np.int16 | np.float32] | None
    type: Literal['audio_chunk'] = 'audio_chunk'

@register_event
@dataclass
class TextEvent():
    text: str
    type: Literal['text'] = 'text'

@register_event
@dataclass
class ControlEvent():
    type: Literal['start_session', 'end_session', 'error']
    data: Optional[Any] = None

@dataclass
class TranscriptionEvent():
    type: Literal['delta', 'transcription_completed', 'speech_started', 'speech_stopped']
    text: Optional[str] = None

@dataclass
class TTSEvent():
    text: str


