import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from events import (
    make_event,
    TextEvent,
    AudioEvent,
    ControlEvent,
    InputAudioTranscriptionCompletedEvent,
    InputAudioTranscriptionFailedEvent,
)


def test_make_text_event_from_json():
    payload = {"type": "text", "text": "hello"}
    event = make_event(json.loads(json.dumps(payload)))
    assert isinstance(event, TextEvent)
    assert event.text == "hello"
    assert event.type == "text"


def test_make_control_event_extra_fields_ignored():
    payload = {"type": "end_session", "data": {"reason": "done"}, "extra": 42}
    event = make_event(json.loads(json.dumps(payload)))
    assert isinstance(event, ControlEvent)
    assert event.type == "end_session"
    assert event.data == {"reason": "done"}
    assert not hasattr(event, "extra")


def test_make_audio_event_from_json():
    payload = {"type": "audio_chunk", "data": [1, 2, 3]}
    event = make_event(json.loads(json.dumps(payload)))
    assert isinstance(event, AudioEvent)
    # make_event does not convert to numpy array automatically
    assert event.data == [1, 2, 3]


def test_make_event_unknown_type():
    payload = {"type": "unknown"}
    with pytest.raises(ValueError):
        make_event(json.loads(json.dumps(payload)))


def test_make_transcription_completed_event():
    payload = {
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "hello world",
    }
    evt = make_event(json.loads(json.dumps(payload)))
    assert isinstance(evt, InputAudioTranscriptionCompletedEvent)
    assert evt.transcript == "hello world"


def test_make_transcription_failed_event():
    payload = {
        "type": "conversation.item.input_audio_transcription.failed",
        "error": "oops",
    }
    evt = make_event(json.loads(json.dumps(payload)))
    assert isinstance(evt, InputAudioTranscriptionFailedEvent)
    assert evt.error == "oops"
