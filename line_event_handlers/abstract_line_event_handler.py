import os
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.models import (
    TextSendMessage,
)
import abc

from CommandException import CommandException

__all__ = (
    'line_bot_api', 'handler',
    'push_message', 'reply_message',
    'AbstractLineEventHandler')

line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))


def push_message(to, message_text):
    line_bot_api.push_message(
        to,
        TextSendMessage(text=message_text))


def reply_message(reply_token, message_text):
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text=message_text))


class AbstractLineEventHandler(abc.ABC):
    HELP_MESSAGE = str

    def __init__(self):
        pass

    def handle_event(self, event):
        sender_id = event.source.sender_id
        message = event.message.text
        commands = message.split(' ')

        reply_token = event.reply_token
        if reply_token != '00000000000000000000000000000000':
            try:
                messages = self._map_action(commands)(sender_id=sender_id, commands=commands)

                if isinstance(messages, str):
                    reply_message(reply_token, messages)
                elif isinstance(messages, list):
                    for message in messages:
                        push_message(sender_id, message)
            except CommandException as e:
                reply_message(reply_token, str(e))
            except Exception as e:
                reply_message(reply_token, '系統異常')
                # self.reply_message(reply_token, str(e))

    @abc.abstractmethod
    def _map_action(self, commands):
        return NotImplemented

    @staticmethod
    @abc.abstractmethod
    def help_message():
        return NotImplemented
