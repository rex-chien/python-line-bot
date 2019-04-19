import re
from datetime import (
    datetime, date, timedelta
)
import requests
import json
from bs4 import BeautifulSoup

from .abstract_line_bot import AbstractLineMessageHandler
from CommandException import CommandException

mops_api_prefix = 'http://mops.twse.com.tw/mops/web'
headers = {
    'Host': 'mops.twse.com.tw',
    'Origin': 'http://mops.twse.com.tw',
    'Referer': 'http://mops.twse.com.tw/mops/web/t146sb05',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'
}

detail_payload_re = r"^document.t05st01_fm.(.+).value='(.+)'$"


class MopsLineMessageHandler(AbstractLineMessageHandler):
    def __init__(self):
        super().__init__()

    def _map_action(self, commands):
        actions = {
            'recent': self._recent_action,
            'range': self._range_action,
            'help': self._help_action,
        }
        command = commands[1].lower()
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

        messages = self.retrieve_material_information_within_date_range(company_code, begin_date)

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

        messages = self.retrieve_material_information_within_date_range(company_code, begin_date, end_date)

        if not messages:
            return f'[{company_code}] 於 [{begin_date.strftime("%Y-%m-%d")}~{end_date.strftime("%Y-%m-%d")}] 天無重大訊息'

        return messages

    def _help_action(self, **kwargs):
        return self.help_message()

    def retrieve_material_information_within_date_range(self, company_code, begin_date, end_date=date.today()):
        parameters = []

        while end_date >= begin_date:
            parameter = Parameter()
            parameter.year = end_date.year - 1911
            parameter.month = end_date.month
            parameter.end_day = end_date.day
            parameter.begin_day = 1

            parameters.append(parameter)

            del parameter

            end_date = end_date - timedelta(days=end_date.day)
        else:
            parameters[-1].begin_day = begin_date.day

        messages = []
        detail_payloads = []

        for param in parameters:
            payload = {
                'encodeURIComponent': 1,
                'step': 1,
                'firstin': 1,
                'off': 1,
                'queryName': 'co_id',
                'inpuType': 'co_id',
                'TYPEK': 'all',
                'co_id': company_code,
                'year': param.year,
                'month': param.month,
                'b_date': param.begin_day,
                'e_date': param.end_day
            }

            payload_hash_key = to_sha1(json.dumps(payload))
            detail_payloads_str = self.redis_cache.get(payload_hash_key)
            local_detail_payloads = []
            if detail_payloads_str is not None:
                local_detail_payloads = json.loads(detail_payloads_str)
                detail_payloads = detail_payloads + local_detail_payloads
                continue

            soup = soup_from_mops(payload)
            all_tables = soup.find_all('table')
            if not all_tables or len(all_tables) < 2:
                continue

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
                    'year': param.year
                }

                for assignment in onclick_assignments:
                    m = re.search(detail_payload_re, assignment)
                    if m:
                        matched_groups = m.groups()
                        detail_payload[matched_groups[0]] = matched_groups[1]

                local_detail_payloads.append(detail_payload)

            self.redis_cache.setex(payload_hash_key, 60 * 60, json.dumps(local_detail_payloads))
            detail_payloads = detail_payloads + local_detail_payloads

        for detail_payload in detail_payloads:
            detail_payload_hash_key = to_sha1(json.dumps(detail_payload))
            material_info_str = self.redis_cache.get(detail_payload_hash_key)
            if material_info_str is not None:
                material_info = MaterialInformation(**json.loads(material_info_str))
            else:
                soup = soup_from_mops(detail_payload)
                information_body_table = soup.find_all('table')[2]
                rows = information_body_table.find_all('tr')

                material_info = MaterialInformation()
                material_info.spoken_date = rows[0].find_all('td')[3].text.strip()
                material_info.fact_date = rows[3].find_all('td')[3].text.strip()
                material_info.title = rows[2].find_all('td')[1].text.strip()
                material_info.content = rows[4].find_all('td')[1].text.strip()

            self.redis_cache.setex(detail_payload_hash_key, 60 * 60 * 24, json.dumps(material_info.__dict__))

            messages.append(f'【發言日期】{material_info.spoken_date}'
                            f'\n【事實發生日】{material_info.fact_date}'
                            f'\n【主旨】\n{material_info.title}'
                            f'\n【說明】\n{material_info.content}'[:2000])

        return messages

    @staticmethod
    def help_message():
        return '==重大訊息==\n' \
               '【指令說明】\n' + \
               '查詢今天重大訊息：MI [公司代號] RECENT\n' + \
               '查詢近 N 天重大訊息：MI [公司代號] RECENT [N]\n' + \
               '查詢指定日期後的重大訊息：MI [公司代號] RANGE [YYYYMMDD]\n' + \
               '查詢指定日期範圍中的重大訊息：MI [公司代號] RANGE [YYYYMMDD] [YYYYMMDD]\n' + \
               '顯示指令說明：MI HELP\n' + \
               '【資料來源】\n' + \
               '公開資訊觀測站：http://mops.twse.com.tw/mops/web/index'


def soup_from_mops(payload):
    page_source = requests.get(mops_api_prefix + '/ajax_t05st01', params=payload, headers=headers).text
    soup = BeautifulSoup(page_source, 'html.parser')

    return soup


def to_sha1(text):
    import hashlib
    encoder = hashlib.sha1(text.encode(encoding='utf-8'))
    return encoder.hexdigest()


class MaterialInformation:
    spoken_date = None
    fact_date = None
    title = None
    content = None

    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)


class Parameter:
    year = None
    month = None
    begin_day = None
    end_day = None
