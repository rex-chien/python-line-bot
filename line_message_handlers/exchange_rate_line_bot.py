import twder
from linebot.models import (
    TextSendMessage,
)

from .abstract_line_bot import AbstractLineMessageHandler


class ExchangeRateLineMessageHandler(AbstractLineMessageHandler):
    collection = None

    def __init__(self):
        super().__init__()
        self.collection = super().get_collection('exchange_reports')

    def start_schedule_task(self):
        now_all = twder.now_all()
        currency_names_dict = twder.currency_name_dict()

        results = self.collection.find({})

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
                self.line_bot_api.push_message(
                    r['source'],
                    TextSendMessage(text='【匯率到價提醒】\n' + '\n'.join(notify_messages))
                )
                self.collection.replace_one({'source': r['source']}, r, upsert=True)

    def handle_event(self, event):
        sender_id = event.source.sender_id
        message = event.message.text
        commands = message.split(' ')
        
        reply_message = self.__command_actions(commands[0])(sender_id=sender_id, commands=commands)

        if event.reply_token != '00000000000000000000000000000000':
            self.line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_message))

    def __command_actions(self, command):
        actions = {
            'set': self.__set_action,
            'del': self.__del_action,
            'get': self.__get_action,
            'help': self.__help_action,
        }
        command = command.lower()
        if command not in actions:
            command = 'help'
        return actions[command]

    def __set_action(self, **kwargs):
        sender_id = kwargs['sender_id']
        commands = kwargs['commands']
        currency = commands[1].upper()
        rate = float(commands[2])
        rate_type = 'buy' if commands[3].upper() == 'B' else 'sell'

        exchange_report = self.collection
        r = exchange_report.find_one({'source': sender_id})

        if r is None:
            r = {
                'source': sender_id,
                'notify_rates': {}
            }

        notify_rate = r['notify_rates'].get(currency, {})
        notify_rate[rate_type] = {'rate': rate, 'notified': False}
        r['notify_rates'][currency] = notify_rate

        exchange_report.replace_one({'source': sender_id}, r, upsert=True)

        return '匯率到價提醒設定成功！'

    def __del_action(self, **kwargs):
        sender_id = kwargs['sender_id']
        commands = kwargs['commands']
        currency = commands[1].upper()
        rate_type = 'buy' if commands[2].upper() == 'B' else 'sell'

        exchange_report = self.collection
        r = exchange_report.find_one({'source': sender_id})

        if r is None:
            r = {
                'source': sender_id,
                'notify_rates': {}
            }

        notify_rate = r['notify_rates'].get(currency, {})
        notify_rate.pop(rate_type, 0)
        r['notify_rates'][currency] = notify_rate

        exchange_report.replace_one({'source': sender_id}, r, upsert=True)

        return '匯率到價提醒刪除成功！'

    def __get_action(self, **kwargs):
        commands = kwargs['commands']
        currency = commands[1].upper()
        rates = twder.now(currency)
        currency_names_dict = twder.currency_name_dict()
        quote_time, cash_buy, cash_sell, rate_buy, rate_sell = rates
        str_format = '【{currency_name}】\n' + \
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

    def __help_action(self, **kwargs):
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
