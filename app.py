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

from line_message_handlers import ExchangeRateLineMessageHandler

load_dotenv()

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

exchange_rate_message_handler = ExchangeRateLineMessageHandler()


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # line_bot_api.push_message('U8d73bbf97b603c77edfeffce883f1d68', TextSendMessage(text='Hello World!'))

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    exchange_rate_message_handler.handle_event(event)


@app.route('/')
def hello_world():
    return 'hello world!'


if __name__ == '__main__':
    app.run()

import atexit

from apscheduler.schedulers.background import BackgroundScheduler


def scheduled_report():
    exchange_rate_message_handler.start_schedule_task()


scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_report, trigger="interval", minutes=1)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())
