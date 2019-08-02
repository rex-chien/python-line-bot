import re
from datetime import (
    datetime, date, timedelta
)
import requests
import json
from bs4 import BeautifulSoup
from mongoengine import DoesNotExist
import os

from line_event_handlers.abstract_line_event_handler import AbstractLineEventHandler, push_message
from domain import MaterialInformation, MaterialInformationSubscription
from CommandException import CommandException
from persistence import redis_cache

mops_api_prefix = 'http://mops.twse.com.tw/mops/web'
headers = {
    'Host': 'mops.twse.com.tw',
    'Origin': 'http://mops.twse.com.tw',
    'Referer': 'http://mops.twse.com.tw/mops/web/t146sb05',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'
}

detail_payload_re = r"^document.t05st01_fm.(.+).value='(.+)'$"

__all__ = ('MopsEventHandler', 'retrieve_material_information_within_date_range', 'start_mops_schedule_task')


class MopsEventHandler(AbstractLineEventHandler):
    def __init__(self):
        super().__init__()

    def _map_action(self, commands):
        actions = {
            'recent': self._recent_action,
            'range': self._range_action,
            'sub': self._subscribe_action,
            'help': self._help_action,
        }
        if len(commands) > 1:
            command = commands[1].lower()
        else:
            command = commands[0].lower()

        if command not in actions:
            command = 'help'
        return actions[command]

    def _recent_action(self, **kwargs):
        commands = kwargs['commands']

        company_code = commands[0]
        prev_n_days = 1
        if len(commands) > 2:
            prev_n_days = int(commands[2])

        if prev_n_days < 1:
            raise CommandException('天數必須大於 1')

        begin_date = date.today()
        begin_date = begin_date + timedelta(days=-prev_n_days + 1)

        material_information_list = retrieve_material_information_within_date_range(
            company_code=company_code, begin_date=begin_date)
        messages = list(map(format_line_message, material_information_list))

        if not messages:
            return f'[{company_code}] 近 [{prev_n_days} 天] 無重大訊息'

        return messages

    def _range_action(self, **kwargs):
        commands = kwargs['commands']
        end_date = date.today()

        company_code = commands[0]
        begin_date_str = commands[2]
        begin_date = datetime.strptime(begin_date_str, '%Y%m%d').date()
        if len(commands) > 3:
            end_date_str = commands[3]
            end_date = datetime.strptime(end_date_str, '%Y%m%d').date()

        if begin_date > end_date:
            raise CommandException('起始日期不可以晚於結束日期' if len(commands) > 3 else '起始日期不可以晚於今天')

        if (end_date - begin_date).days > 90:
            raise CommandException('日期範圍須在 90 天內')

        material_information_list = retrieve_material_information_within_date_range(
            company_code=company_code, begin_date=begin_date, end_date=end_date)
        messages = list(map(format_line_message, material_information_list))

        if not messages:
            return f'[{company_code}] 於 [{begin_date.strftime("%Y-%m-%d")}~{end_date.strftime("%Y-%m-%d")}] 天無重大訊息'

        return messages

    def _subscribe_action(self, **kwargs):
        sender_id = kwargs['sender_id']
        commands = kwargs['commands']
        company_code = commands[0]

        MaterialInformationSubscription.objects(id=company_code).upsert_one(add_to_set__sources=sender_id)

        return f'成功訂閱 [{company_code}] 的重大訊息'

    def _help_action(self, **kwargs):
        return self.help_message()

    @staticmethod
    def help_message():
        return '==重大訊息==\n' \
               '【指令說明】\n' + \
               '查詢今天重大訊息：MI [公司代號] RECENT\n' + \
               '查詢近 N 天重大訊息：MI [公司代號] RECENT [N]\n' + \
               '查詢指定日期後的重大訊息：MI [公司代號] RANGE [YYYYMMDD]\n' + \
               '查詢指定日期範圍中的重大訊息：MI [公司代號] RANGE [YYYYMMDD] [YYYYMMDD]\n' + \
               '訂閱指定公司的重大訊息：MI [公司代號] SUB\n' + \
               '顯示指令說明：MI HELP\n' + \
               '【資料來源】\n' + \
               '公開資訊觀測站：http://mops.twse.com.tw/mops/web/index'


application_url_root = os.getenv('APPLICATION_URL_ROOT')


def format_line_message(material_info: MaterialInformation):
    return f'【發言日期】{material_info.spoken_roc_date}' \
        f'\n【事實發生日】{material_info.fact_roc_date}' \
        f'\n【主旨】\n{material_info.title}' \
        f'\n{application_url_root}/mi/{material_info.id}'


def soup_from_mops(payload):
    page_source = requests.get(mops_api_prefix + '/ajax_t05st01', params=payload, headers=headers).text
    soup = BeautifulSoup(page_source, 'html.parser')

    return soup


def to_sha1(text):
    import hashlib
    encoder = hashlib.sha1(text.encode(encoding='utf-8'))
    return encoder.hexdigest()


def retrieve_material_information_within_date_range(company_code, begin_date, end_date=date.today()):
    years = get_years_range(begin_date, end_date)

    detail_payloads = []

    for year in years:
        detail_payloads += get_detail_payloads(company_code, year)

    return read_material_info_details(detail_payloads, begin_date, end_date)


def get_detail_payloads(company_code, year):
    payload = {
        'encodeURIComponent': 1,
        'step': 1,
        'firstin': 1,
        'off': 1,
        'queryName': 'co_id',
        'inpuType': 'co_id',
        'TYPEK': 'all',
        'co_id': company_code,
        'year': year
    }
    payload_hash_key = to_sha1(json.dumps(payload))
    detail_payloads_str = redis_cache.get_val(payload_hash_key)
    if detail_payloads_str is not None:
        return json.loads(detail_payloads_str)

    soup = soup_from_mops(payload)
    all_tables = soup.find_all('table')
    if not all_tables or len(all_tables) < 2:
        return []

    detail_payloads = []
    material_information_table = all_tables[1]
    for information_row in material_information_table.find_all('tr')[1:]:
        button_column = information_row.find_all('td')[5]
        button = button_column.find('input')

        onclick = button['onclick']
        onclick_assignments = list(filter(None, onclick.split(';')))
        onclick_assignments = onclick_assignments

        detail_payload = {
            'encodeURIComponent': 1,
            'firstin': 1,
            'off': 1,
            'first': 1,
            'step': 2,
            'co_id': company_code,
            'year': year
        }

        for assignment in onclick_assignments:
            m = re.search(detail_payload_re, assignment)
            if m:
                matched_groups = m.groups()
                detail_payload[matched_groups[0]] = matched_groups[1]

        detail_payloads.append(detail_payload)
    redis_cache.set_val(payload_hash_key, 60 * 60, json.dumps(detail_payloads))
    return detail_payloads


def get_years_range(begin_date, end_date):
    years = []
    tmp_end_date = date(end_date.year, end_date.month, end_date.day)
    while tmp_end_date >= begin_date:
        years.append(tmp_end_date.year - 1911)
        tmp_end_date = end_date - timedelta(days=tmp_end_date.timetuple().tm_yday)
    return years


def read_material_info_details(detail_payloads, begin_date, end_date):
    material_info_list = []

    for detail_payload in detail_payloads:
        spoken_date = datetime.strptime(detail_payload['spoke_date'], '%Y%m%d').date()

        if spoken_date > end_date:
            break

        if spoken_date >= begin_date:
            plain_key = f"{detail_payload['co_id']}.{detail_payload['year']}." \
                f"{detail_payload['spoke_date']}.{detail_payload['seq_no']}"
            detail_payload_hash_key = to_sha1(plain_key)

            try:
                material_info = MaterialInformation.objects.get(id=detail_payload_hash_key)
            except DoesNotExist:
                soup = soup_from_mops(detail_payload)
                information_body_table = soup.find_all('table')[2]
                rows = information_body_table.find_all('tr')

                material_info = MaterialInformation()
                material_info.id = detail_payload_hash_key
                material_info.company_code = int(detail_payload['co_id'])

                spoken_roc_date_str = rows[0].find_all('td')[3].text.strip()
                spoken_date_str = spoken_roc_date_str.replace(spoken_roc_date_str[:3],
                                                              str(int(spoken_roc_date_str[:3]) + 1911))
                spoken_time_str = rows[0].find_all('td')[5].text.strip()
                material_info.spoken_at = datetime.strptime(f'{spoken_date_str} {spoken_time_str}', '%Y/%m/%d %H:%M:%S')

                material_info.speaker = rows[1].find_all('td')[1].text.strip()
                material_info.speaker_title = rows[1].find_all('td')[3].text.strip()
                material_info.speaker_phone = rows[1].find_all('td')[5].text.strip()

                material_info.terms = rows[3].find_all('td')[1].text.strip().replace('\n', ' ')

                fact_roc_date_str = rows[3].find_all('td')[3].text.strip()
                fact_date_str = fact_roc_date_str.replace(fact_roc_date_str[:3],
                                                          str(int(fact_roc_date_str[:3]) + 1911))
                material_info.fact_date = datetime.strptime(fact_date_str, '%Y/%m/%d')

                material_info.title = rows[2].find_all('td')[1].text.strip()
                material_info.content = rows[4].find_all('td')[1].text.strip()

                material_info.save()

            material_info_list.append(material_info)

    return material_info_list


def start_mops_schedule_task():
    today = date.today()
    subscriptions = MaterialInformationSubscription.objects()

    for subscription in subscriptions:
        company_code = subscription.company_code
        last_pushed_id = subscription.last_pushed_id

        infomations = retrieve_material_information_within_date_range(company_code, today)

        for index, info in enumerate(infomations):
            if info.id == last_pushed_id:
                break
        else:
            index = -1

        for unpushed_info in infomations[index + 1:]:
            for source in subscription.sources:
                push_message(
                    source,
                    format_line_message(unpushed_info)
                )
            last_pushed_id = unpushed_info.id

        subscription.last_pushed_id = last_pushed_id
        subscription.save()


