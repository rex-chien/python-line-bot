import json

import twder
from mongoengine import DoesNotExist
from mongoengine.queryset.visitor import Q

from domain import ExchangeNotification, Notification, NotificationFlag
from line_message_handlers.abstract_line_bot import AbstractLineMessageHandler, push_message
from persistence import redis_cache

__all__ = ('ExchangeRateLineMessageHandler', 'start_schedule_task')


def cache_currency_name_dic():
    twder_currency_name_dict_key = 'twder.currency_name_dict'
    currency_name_dict_str = redis_cache.get_val(twder_currency_name_dict_key)
    if currency_name_dict_str is None:
        currency_name_dict = twder.currency_name_dict()
        currency_name_dict_str = json.dumps(currency_name_dict)
        # 1 day
        redis_cache.set_val(twder_currency_name_dict_key, 60 * 60 * 24, currency_name_dict_str)

    return json.loads(currency_name_dict_str)


def cache_now_all():
    twder_now_all_key = 'twder.now_all'
    now_all_str = redis_cache.get_val(twder_now_all_key)
    if now_all_str is None:
        now_all = twder.now_all()
        now_all_str = json.dumps(now_all)
        # 10 minutes
        redis_cache.set_val(twder_now_all_key, 60 * 10, now_all_str)

    return json.loads(now_all_str)


def cache_now(currency):
    return cache_now_all()[currency]


def start_schedule_task():
    now_all = cache_now_all()
    currency_names_dict = cache_currency_name_dic()

    notifications = ExchangeNotification.objects(
        Q(notify_rates__sell__notified=False) | Q(notify_rates__buy__notified=False))

    for notification in notifications:
        notify_rates = notification.notify_rates
        notify_messages = []
        for notify_rate in notify_rates:
            currency = notify_rate.currency

            buy_flag = notify_rate.buy
            if buy_flag and not buy_flag.notified:
                if now_all[currency][3] != '-' and float(now_all[currency][3]) >= notify_rate.buy.rate:
                    notify_messages.append(currency_names_dict[currency] + ' 買入: ' + now_all[currency][3])
                    notify_rate.buy.notified = True
            # if 'buy' in notify_rate and not notify_rate['buy']['notified']:
            #     pass

            sell_flag = notify_rate.sell
            if sell_flag and not sell_flag.notified:
                if now_all[currency][4] != '-' and float(now_all[currency][4]) <= notify_rate.sell.rate:
                    notify_messages.append(currency_names_dict[currency] + ' 賣出: ' + now_all[currency][4])
                    notify_rate.sell.notified = True
            # if 'sell' in notify_rate and not notify_rate['sell']['notified']:
            #     pass

        if notify_messages:
            push_message(
                notification.source,
                '【匯率到價提醒】\n' + '\n'.join(notify_messages)
            )
            notification.save()
            # self.collection.replace_one({'source': notification['source']}, notification, upsert=True)


class ExchangeRateLineMessageHandler(AbstractLineMessageHandler):
    def __init__(self):
        super().__init__()

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

        try:
            r = ExchangeNotification.objects.get(source=sender_id)
        except DoesNotExist:
            r = ExchangeNotification(source=sender_id, notify_rates=[])

        notify_rate = next((x for x in r.notify_rates if x.currency == currency), None)
        if not notify_rate:
            notify_rate = Notification(currency=currency)
            r.notify_rates.append(notify_rate)
        notification_flag = NotificationFlag(rate=rate, notified=False)

        if rate_type == 'buy':
            notify_rate.buy = notification_flag
        elif rate_type == 'sell':
            notify_rate.sell = notification_flag

        r.save()

        return '匯率到價提醒設定成功！'

    def _del_action(self, **kwargs):
        sender_id = kwargs['sender_id']
        commands = kwargs['commands']
        currency = commands[1].upper()
        rate_type = 'buy' if commands[2].upper() == 'B' else 'sell'

        try:
            r = ExchangeNotification.objects.get(source=sender_id)

            notify_rate = next((x for x in r.notify_rates if x.currency == currency), None)
            if notify_rate:
                if rate_type == 'buy':
                    notify_rate.buy = None
                elif rate_type == 'sell':
                    notify_rate.sell = None

            r.save()

        except DoesNotExist:
            pass

        return '匯率到價提醒刪除成功！'

    def _get_action(self, **kwargs):
        commands = kwargs['commands']
        currency = commands[1].upper()
        rates = cache_now(currency)
        currency_names_dict = cache_currency_name_dic()
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
