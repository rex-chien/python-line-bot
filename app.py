import os

import requests
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, abort, render_template, make_response
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage)

from line_event_handlers import *
import domain

app = Flask(__name__)

exchange_rate_message_handler = ExchangeRateEventHandler()
mops_message_handler = MopsEventHandler()


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
    if command == 'er':
        exchange_rate_message_handler.handle_event(event)
    elif command == 'mi':
        mops_message_handler.handle_event(event)
    else:
        reply_message(event.reply_token,
                      ExchangeRateEventHandler.help_message()
                      + '\n\n'
                      + MopsEventHandler.help_message())


@app.route('/')
def hello_world():
    return 'hello world!'


@app.route('/mi/<material_info_id>')
def mi_detail(material_info_id):
    try:
        material_info = domain.MaterialInformation.objects.get(id=material_info_id)
        return render_template('mi_detail.html', material_info=material_info)
    except:
        return render_template('404.html'), 404


# @app.errorhandler(404)
# def page_not_found(error):
#     return render_template('404.html'), 404


if __name__ == '__main__':
    app.run()

import atexit

from apscheduler.schedulers.background import BackgroundScheduler


def scheduled_report():
    start_schedule_task()


def wakeup():
    requests.get(os.getenv('WAKEUP_URL'))


scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_report, trigger="interval", minutes=1)
# scheduler.add_job(func=scheduled_report, trigger="interval", seconds=10)
scheduler.add_job(func=wakeup, trigger="interval", minutes=10)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())
