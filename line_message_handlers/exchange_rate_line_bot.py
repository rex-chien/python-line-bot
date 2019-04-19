import json

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
        now_all = self.cache_now_all()
        currency_names_dict = self.cache_currency_name_dic()

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

    # def handle_event(self, event):
    #     sender_id = event.source.sender_id
    #     message = event.message.text
    #     commands = message.split(' ')
    #
    #     reply_message = self.__command_actions(commands[0])(sender_id=sender_id, commands=commands)
    #
    #     if event.reply_token != '00000000000000000000000000000000':
    #         self.line_bot_api.reply_message(
    #             event.reply_token,
    #             TextSendMessage(text=reply_message))

    @staticmethod
    def help_message():
        return '==台灣銀行牌告匯率==\n' \
               '【指令說明】\n' + \
               '設定匯率到價提醒：ER SET [幣別] [匯率] [B/S]\n' + \
               '刪除匯率到價提醒：ER DEL [幣別] [B/S]\n' + \
               '取得即期匯率：ER GET [幣別]\n' + \
               '顯示指令說明：ER HELP\n' + \
               '* [B/S] B=銀行買入/S=銀行賣出\n' + \
               '【資料來源】\n' + \
               '臺灣銀行牌告匯率：http://rate.bot.com.tw/xrt?Lang=zh-TW'

    def _map_action(self, commands):
        actions = {
            'set': self._set_action,
            'del': self._del_action,
            'get': self._get_action,
            'help': self._help_action,
        }
        command = commands[0].lower()
        if command not in actions:
            command = 'help'
        return actions[command]

    def _set_action(self, **kwargs):
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

    def _del_action(self, **kwargs):
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

    def _get_action(self, **kwargs):
        commands = kwargs['commands']
        currency = commands[1].upper()
        rates = self.cache_now(currency)
        currency_names_dict = self.cache_currency_name_dic()
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

    def _help_action(self, **kwargs):
        return self.help_message()

    def cache_now_all(self):
        twder_now_all_key = 'twder.now_all'
        now_all_str = self.redis_cache.get(twder_now_all_key)
        if now_all_str is None:
            now_all = twder.now_all()
            now_all_str = json.dumps(now_all)
            # 10 minutes
            self.redis_cache.setex(twder_now_all_key, 60 * 10, now_all_str)

        return json.loads(now_all_str)

    def cache_now(self, currency):
        return self.cache_now_all()[currency]

    def cache_currency_name_dic(self):
        twder_currency_name_dict_key = 'twder.currency_name_dict'
        currency_name_dict_str = self.redis_cache.get(twder_currency_name_dict_key)
        if currency_name_dict_str is None:
            currency_name_dict = twder.currency_name_dict()
            currency_name_dict_str = json.dumps(currency_name_dict)
            # 1 day
            self.redis_cache.setex(twder_currency_name_dict_key, 60 * 60 * 24, currency_name_dict_str)

        return json.loads(currency_name_dict_str)
