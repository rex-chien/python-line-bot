import requests
from bs4 import BeautifulSoup
import re
from datetime import (
    datetime, date, timedelta
)
from linebot.models import (
    TextSendMessage,
)

from .abstract_line_bot import AbstractLineMessageHandler

mops_api_prefix = 'http://mops.twse.com.tw/mops/web'
headers = {
    'Host': 'mops.twse.com.tw',
    'Origin': 'http://mops.twse.com.tw',
    'Referer': 'http://mops.twse.com.tw/mops/web/t146sb05',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'
}

detail_payload_re = r"^document.fm1.(.+).value='(.+)'$"


class MopsLineMessageHandler(AbstractLineMessageHandler):
    def __init__(self):
        super().__init__()

    def handle_event(self, event):
        message = event.message.text.strip()

        if message.lower() == 'help':
            reply_text = '【指令說明】\n' + \
                         '查詢近七天重大訊息：MOPS [公司代號]\n' + \
                         '顯示指令說明：MOPS HELP\n' + \
                         '【資料來源】\n' + \
                         '公開資訊觀測站：http://mops.twse.com.tw/mops/web/index'
            self.line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text))
            return

        stock_code = message
        payload = {
            'encodeURIComponent': 1,
            'step': 1,
            'firstin': 1,
            'off': 1,
            'queryName': 'co_id',
            'inpuType': 'co_id',
            'TYPEK': 'all',
            'co_id': stock_code
        }
        page_source = requests.get(mops_api_prefix + '/ajax_t146sb05', params=payload, headers=headers).text
        soup = BeautifulSoup(page_source, 'html.parser')
        material_information_table = soup.find_all('table')[1]
        information_date_range = date.today() - timedelta(days=6)
        has_information_recently = False

        original_form = soup.find('form', id='fm1')
        typek = original_form.find('input', id='TYPEK')['value']

        for information_row in material_information_table.find_all('tr')[1:]:
            title_column = information_row.find_all('td')[1]
            title_button = title_column.find('button')
            onclick = title_button['onclick']
            onclick_assignments = list(filter(None, onclick.split(';')))
            onclick_assignments = onclick_assignments[:len(onclick_assignments) - 2]  # only need values setting

            detail_payload = {
                'encodeURIComponent': 1,
                'firstin': 'true',
                'off': 1,
                'first': 'true',
                'TYPEK': typek,
                'co_id': stock_code
            }

            for assignment in onclick_assignments:
                m = re.search(detail_payload_re, assignment)
                if m:
                    matched_groups = m.groups()
                    detail_payload[matched_groups[0]] = matched_groups[1]

            # material_information_redis_key = f"{detail_payload['co_id']}{detail_payload['seq_no']}{detail_payload['spoke_date']}{detail_payload['spoke_time']}"
            # self.redis_cache.get(material_information_redis_key)

            page_source = requests.get(mops_api_prefix + '/ajax_t05st01', params=detail_payload, headers=headers).text
            soup = BeautifulSoup(page_source, 'html.parser')
            information_body_table = soup.find_all('table')[2]
            rows = information_body_table.find_all('tr')

            spoken_date = rows[0].find_all('td')[3].text.strip()

            spoken_date_in_bc = spoken_date.replace(spoken_date[0:3], str(int(spoken_date[0:3]) + 1911))
            if datetime.strptime(spoken_date_in_bc, '%Y/%m/%d').date() < information_date_range:
                break
            has_information_recently = True

            title = rows[2].find_all('td')[1].text.strip()
            fact_date = rows[3].find_all('td')[3].text.strip()
            content = rows[4].find_all('td')[1].text.strip()

            self.line_bot_api.push_message(
                event.source.sender_id,
                TextSendMessage(
                    text=(f'【發言日期】{spoken_date}'
                          f'\n【事實發生日】{fact_date}'
                          f'\n【主旨】\n{title}'
                          f'\n【說明】\n{content}')[:2000]))

        if not has_information_recently:
            self.line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f'公司代碼: {stock_code}，近七天無重大訊息'))
