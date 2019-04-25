import unittest
from unittest.mock import MagicMock, patch
import datetime

import os

from linebot.models import MessageEvent, TextMessage, SourceUser

fake_os_environ = {
    'CHANNEL_ACCESS_TOKEN': 'channelaccesstoken',
    'CHANNEL_SECRET': 'channelsecret',
    'MONGODB_DATABASE': 'mongoenginetest',
    'MONGODB_URI': 'mongomock://localhost',
    'REDIS_URL': 'redis://localhost'
}

fake_today = datetime.date(2019, 3, 4)


class FakeDate(datetime.date):
    @classmethod
    def today(cls):
        return cls(fake_today.year, fake_today.month, fake_today.day)


datetime.date = FakeDate

with patch.dict(os.environ, fake_os_environ):
    from line_event_handlers import *


    class TestMopsLineBot(unittest.TestCase):
        handler = None
        message_event = None

        def setUp(self):
            self.handler = MopsEventHandler()
            self.message_event = MessageEvent()
            self.message_event.reply_token = 'replytoken'
            self.message_event.source = SourceUser(user_id='userid')

            self.push_message = patch(
                'line_event_handlers.abstract_line_event_handler.push_message',
                MagicMock()).start()
            self.reply_message = patch(
                'line_event_handlers.abstract_line_event_handler.reply_message',
                MagicMock()).start()
            self.retrieve_material_information_within_date_range = patch(
                'line_event_handlers.mops_event_handler.retrieve_material_information_within_date_range',
                MagicMock()).start()

        def tearDown(self):
            patch.stopall()

        def testRecentAction(self):
            self.givenCommandShouldRetrieveWith_CompanyCode_BeginDate_EndDate(
                command='2330 RECENT',
                company_code='2330',
                begin_date=fake_today
            )

        def testRecent7Action(self):
            self.givenCommandShouldRetrieveWith_CompanyCode_BeginDate_EndDate(
                command='2330 RECENT 7',
                company_code='2330',
                begin_date=fake_today - datetime.timedelta(days=6)
            )

        def testRange20190101To20190304(self):
            self.givenCommandShouldRetrieveWith_CompanyCode_BeginDate_EndDate(
                command='2330 RANGE 20190101 20190304',
                company_code='2330',
                begin_date=datetime.date(2019, 1, 1),
                end_date=datetime.date(2019, 3, 4)
            )

        def givenCommandShouldRetrieveWith_CompanyCode_BeginDate_EndDate(
                self, command, company_code, begin_date, end_date=None):
            self.message_event.message = TextMessage(text=command)
            self.handler.handle_event(self.message_event)

            if end_date:
                self.retrieve_material_information_within_date_range \
                    .assert_called_once_with(company_code, begin_date, end_date)
            else:
                self.retrieve_material_information_within_date_range \
                    .assert_called_once_with(company_code, begin_date)

        def testHelpAction(self):
            self.message_event.message = TextMessage(text='help')
            self.handler.handle_event(self.message_event)
            self.reply_message.assert_called_once_with('replytoken',
                                                       '==重大訊息==\n'
                                                       '【指令說明】\n'
                                                       '查詢今天重大訊息：MI [公司代號] RECENT\n'
                                                       '查詢近 N 天重大訊息：MI [公司代號] RECENT [N]\n'
                                                       '查詢指定日期後的重大訊息：MI [公司代號] RANGE [YYYYMMDD]\n'
                                                       '查詢指定日期範圍中的重大訊息：MI [公司代號] RANGE [YYYYMMDD] [YYYYMMDD]\n'
                                                       '顯示指令說明：MI HELP\n'
                                                       '【資料來源】\n'
                                                       '公開資訊觀測站：http://mops.twse.com.tw/mops/web/index')

if __name__ == '__main__':
    unittest.main()
