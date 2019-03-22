from flask import Flask, request, abort, jsonify
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
from dotenv import load_dotenv
import os
import twder

from MongoCollection import get_exchange_reports_collection

load_dotenv()

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))


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
    message = event.message.text
    commands = message.split(' ')
    reply_message = command_actions(commands[0])(event, commands)

    if event.reply_token != '00000000000000000000000000000000':
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_message))


def command_actions(command):
    actions = {
        'set': set_action,
        'del': del_action,
        'get': get_action,
        'help': help_action,
    }
    command = command.lower()
    if command not in actions:
        command = 'help'
    return actions[command]


def set_action(event, commands):
    currency = commands[1].upper()
    rate = float(commands[2])
    rate_type = 'buy' if commands[3].upper() == 'B' else 'sell'

    source = event.source.sender_id
    exchange_report = get_exchange_reports_collection()
    r = exchange_report.find_one({'source': source})

    if r is None:
        r = {
            'source': source,
            'notify_rates': {}
        }

    notify_rate = r['notify_rates'].get(currency, {})
    notify_rate[rate_type] = {'rate': rate, 'notified': False}
    r['notify_rates'][currency] = notify_rate

    exchange_report.replace_one({'source': source}, r, upsert=True)

    return '匯率到價提醒設定成功！'


def del_action(event, commands):
    currency = commands[1].upper()
    rate_type = 'buy' if commands[2].upper() == 'B' else 'sell'

    source = event.source.sender_id
    exchange_report = get_exchange_reports_collection()
    r = exchange_report.find_one({'source': source})

    if r is None:
        r = {
            'source': source,
            'notify_rates': {}
        }

    notify_rate = r['notify_rates'].get(currency, {})
    notify_rate.pop(rate_type, 0)
    r['notify_rates'][currency] = notify_rate

    exchange_report.replace_one({'source': source}, r, upsert=True)

    return '匯率到價提醒刪除成功！'


def get_action(event, commands):
    currency = commands[1].upper()
    rates = twder.now(currency)
    currency_names_dict = twder.currency_name_dict()
    quote_time, cash_buy, cash_sell, rate_buy, rate_sell = rates
    str_format = '[{currency_name}]\n' + \
                 '現金買入: {cash_buy}\n' + \
                 '現金賣出: {cash_sell}\n' + \
                 '即期買入: {rate_buy}\n' + \
                 '即期賣出: {rate_sell}'

    return str_format.format(**{
        'currency_name': currency_names_dict[currency],
        'cash_buy': cash_buy,
        'cash_sell': cash_sell,
        'rate_buy': rate_buy,
        'rate_sell': rate_sell,
    })


def help_action(event, commands):
    return '【指令說明】\n' + \
           '設定匯率到價提醒：SET [幣別] [匯率] [B/S]\n' + \
           '刪除匯率到價提醒：DEL [幣別] [B/S]\n' + \
           '取得即期匯率：GET [幣別]\n' + \
           '顯示指令說明：HELP\n' + \
           '* [B/S] B=銀行買入/S=銀行賣出\n' + \
           '【幣別對照】\n' + \
           'USD: 美金、EUR: 歐元、AUD: 澳幣、CAD: 加拿大幣、JPY: 日圓、CNY: 人民幣、GBP: 英鎊、HKD: 港幣\n' + \
           '【資料來源】\n' + \
           '臺灣銀行牌告匯率：http://rate.bot.com.tw/xrt?Lang=zh-TW'


@app.route('/')
def hello_world():
    return jsonify(twder.now_all())


if __name__ == '__main__':
    app.run()

import atexit

from apscheduler.schedulers.background import BackgroundScheduler


def scheduled_report():
    now_all = twder.now_all()
    currency_names_dict = twder.currency_name_dict()

    exchange_report = get_exchange_reports_collection()
    results = exchange_report.find({})

    for r in results:
        notify_rates = r.get('notify_rates', [])
        notify_messages = []
        for currency in notify_rates:
            notify_rate = notify_rates[currency]
            if 'buy' in notify_rate and not notify_rate['buy']['notified']:
                if now_all[currency][3] != '-' and float(now_all[currency][3]) >= notify_rate['buy']['rate']:
                    notify_messages.append(currency_names_dict[currency] + ' 買入: ' + now_all[currency][3])
                    notify_rate['buy']['notified'] = True
            if 'sell' in notify_rate and not notify_rate['sell']['notified']:
                if now_all[currency][4] != '-' and float(now_all[currency][4]) <= notify_rate['sell']['rate']:
                    notify_messages.append(currency_names_dict[currency] + ' 賣出: ' + now_all[currency][4])
                    notify_rate['sell']['notified'] = True

        if notify_messages:
            line_bot_api.push_message(r['source'], TextSendMessage(text='【匯率到價提醒】\n' + '\n'.join(notify_messages)))
            exchange_report.replace_one({'source': r['source']}, r, upsert=True)


scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_report, trigger="interval", seconds=5)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())
