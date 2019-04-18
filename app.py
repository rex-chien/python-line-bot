import os
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, )

import requests

from line_message_handlers import (
    ExchangeRateLineMessageHandler, MopsLineMessageHandler)

load_dotenv()

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

exchange_rate_message_handler = ExchangeRateLineMessageHandler()
mops_message_handler = MopsLineMessageHandler()


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    message = event.message.text
    commands = message.split(' ')
    event.message.text = ' '.join(commands[1:])

    command = commands[0].lower()
    if command == 'twder':
        exchange_rate_message_handler.handle_event(event)
    elif command == 'mops':
        mops_message_handler.handle_event(event)


@app.route('/')
def hello_world():
    return 'hello world!'


if __name__ == '__main__':
    app.run()

import atexit

from apscheduler.schedulers.background import BackgroundScheduler


def scheduled_report():
    exchange_rate_message_handler.start_schedule_task()


def wakeup():
    requests.get(os.getenv('WAKEUP_URL'))


scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_report, trigger="interval", minutes=1)
scheduler.add_job(func=wakeup, trigger="interval", minutes=10)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())
