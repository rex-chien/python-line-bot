import os
import pytest
from _pytest import monkeypatch
from unittest.mock import MagicMock, patch


@pytest.fixture(scope='session', autouse=True)
def _standard_os_environ():
    """Set up ``os.environ`` at the start of the test session to have
    standard values. Returns a list of operations that is used by
    :func:`._reset_os_environ` after each test.
    """
    mp = monkeypatch.MonkeyPatch()
    out = (
        (os.environ, 'CHANNEL_ACCESS_TOKEN', 'channelaccesstoken'),
        (os.environ, 'CHANNEL_SECRET', 'channelsecret'),
        (os.environ, 'MONGODB_DATABASE', 'mongoenginetest'),
        (os.environ, 'MONGODB_URI', 'mongomock://localhost'),
        (os.environ, 'REDIS_URL', 'redis://localhost'),
    )

    for _, key, value in out:
        if value is monkeypatch.notset:
            mp.delenv(key, False)
        else:
            mp.setenv(key, value)

    yield out

    mp.undo()


@pytest.fixture(autouse=True)
def _reset_os_environ(monkeypatch, _standard_os_environ):
    """Reset ``os.environ`` to the standard environ after each test,
    in case a test changed something without cleaning up.
    """
    monkeypatch._setitem.extend(_standard_os_environ)


@pytest.fixture(scope='class')
def setup_handler_tests(request):
    from linebot.models import MessageEvent, SourceUser

    request.cls.push_message = patch(
        'line_event_handlers.abstract_line_event_handler.push_message',
        MagicMock()).start()
    request.cls.reply_message = patch(
        'line_event_handlers.abstract_line_event_handler.reply_message',
        MagicMock()).start()

    message_event = MessageEvent()
    message_event.reply_token = 'replytoken'
    message_event.source = SourceUser(user_id='userid')
    request.cls.message_event = message_event

    yield

    patch.stopall()
