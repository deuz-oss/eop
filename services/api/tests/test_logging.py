import logging

import eop_api.core.logging as logging_module
from eop_api.core.logging import log_event
from eop_api.core.request_context import (
    bind_request_id,
    bind_user_id,
    reset_request_id,
    reset_user_id,
)


class _RecordingLogger:
    def __init__(self):
        self.calls: list[tuple[int, str, dict[str, object]]] = []

    def log(self, level, event, **kw):
        self.calls.append((level, event, kw))


def _patch_logger(monkeypatch) -> _RecordingLogger:
    recorder = _RecordingLogger()
    monkeypatch.setattr(logging_module, "get_logger", lambda name=None: recorder)
    return recorder


def test_log_event_delegates_to_the_configured_logger(monkeypatch):
    recorder = _patch_logger(monkeypatch)

    log_event("something_happened")

    assert len(recorder.calls) == 1
    level, event, _ = recorder.calls[0]
    assert level == logging.INFO
    assert event == "something_happened"


def test_log_event_does_not_create_its_own_logger(monkeypatch):
    calls = []
    monkeypatch.setattr(
        logging_module,
        "get_logger",
        lambda name=None: calls.append(name) or _RecordingLogger(),
    )

    log_event("something_happened")

    assert calls == [None]


def test_log_event_includes_request_id(monkeypatch):
    recorder = _patch_logger(monkeypatch)

    token = bind_request_id("req-abc")
    try:
        log_event("something_happened")
    finally:
        reset_request_id(token)

    _, _, kw = recorder.calls[-1]
    assert kw["request_id"] == "req-abc"


def test_log_event_includes_user_id_when_available(monkeypatch):
    recorder = _patch_logger(monkeypatch)

    token = bind_user_id("user-123")
    try:
        log_event("something_happened")
    finally:
        reset_user_id(token)

    _, _, kw = recorder.calls[-1]
    assert kw["user_id"] == "user-123"


def test_log_event_defaults_user_id_to_none_when_anonymous(monkeypatch):
    recorder = _patch_logger(monkeypatch)

    log_event("something_happened")

    _, _, kw = recorder.calls[-1]
    assert kw["user_id"] is None


def test_log_event_passes_through_custom_fields(monkeypatch):
    recorder = _patch_logger(monkeypatch)

    log_event("order_created", order_id="order-1")

    _, _, kw = recorder.calls[-1]
    assert kw["order_id"] == "order-1"
