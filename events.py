from __future__ import annotations


from typing import (
    Literal,
    Optional,
    Any,
    Type,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
)
from pydantic import BaseModel
from dataclasses import dataclass, fields
import dataclasses

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
    if type_value is None or type_value is dataclasses.MISSING:
        # Support registration based on Literal annotation if no default is provided
        hints = get_type_hints(cls)
        annotated_type = hints.get("type", tfield.type)
        origin = get_origin(annotated_type)
        if origin is Literal:
            for val in get_args(annotated_type):
                if not isinstance(val, str):
                    raise TypeError("'type' literal values must be strings")
                _event_registry[str(val)] = cls
            return cls
        raise ValueError(
            f"Event class {cls.__name__} must have a 'type' field with a default value or class attribute"
        )
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
class OpenAIRealtimeSessionEvent():
    session_id: str
    type: Literal["session.updated",
                    "transcription_session.updated",
                    "session.created",
                    "transcription_session.created"]

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

@register_event
@dataclass
class InputAudioTranscriptionCompletedEvent:
    transcript: str
    type: Literal[
        'conversation.item.input_audio_transcription.completed'
    ] = 'conversation.item.input_audio_transcription.completed'

@register_event
@dataclass
class InputAudioTranscriptionFailedEvent:
    error: Any
    type: Literal[
        'conversation.item.input_audio_transcription.failed'
    ] = 'conversation.item.input_audio_transcription.failed'

@register_event
@dataclass
class ErrorEvent:
    """Generic error event for queue-based APIs."""
    error: Any
    type: Literal['error'] = 'error'

TranscriptionServerEvent: TypeAlias = (
    OpenAIRealtimeSessionEvent
    | InputAudioTranscriptionCompletedEvent
    | InputAudioTranscriptionFailedEvent
)

SessionLifecycleEvent: TypeAlias = OpenAIRealtimeSessionEvent

def make_event(obj: dict[str, Any]) -> Any:
    """
    Given a dict with a 'type' key, look up the right dataclass,
    filter only the fields it expects, and instantiate it.
    """
    t = obj.get("type")
    cls = _event_registry.get(t)
    if cls is None:
        raise ValueError(f"Unknown event type: {t!r}")

    # Pick only the fields that the dataclass defines:
    valid_keys = {f.name for f in fields(cls)}
    init_kwargs = {k: v for k, v in obj.items() if k in valid_keys}

    return cls(**init_kwargs)
