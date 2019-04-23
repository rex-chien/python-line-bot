import unittest
from unittest.mock import MagicMock, patch
from datetime import date

import os

from linebot.models import MessageEvent, TextMessage, SourceUser

with patch.dict(os.environ, {
    'CHANNEL_ACCESS_TOKEN': 'channelaccesstoken',
    'CHANNEL_SECRET': 'channelsecret',
    'MONGODB_DATABASE': 'mongoenginetest',
    'MONGODB_URI': 'mongodb://localhost',
    'REDIS_URL': 'redis://localhost'
}):
    from line_message_handlers import *
    import sys
    a = sys.modules['line_message_handlers']

    class TestMopsLineBot(unittest.TestCase):
        handler = None
        message_event = None
        abstract_line_bot.reply_message = MagicMock
        abstract_line_bot.push_message = MagicMock
        mops_line_bot.retrieve_material_information_within_date_range = MagicMock
        # @patch('line_message_handlers.abstract_line_bot.push_message', MagicMock())
        # @patch('line_message_handlers.abstract_line_bot.reply_message', MagicMock())
        # @patch('line_message_handlers.mops_line_bot.retrieve_material_information_within_date_range', MagicMock())
        def setUp(self):
            self.handler = MopsLineMessageHandler()
            self.message_event = MessageEvent()
            self.message_event.reply_token = 'replytoken'
            self.message_event.source = SourceUser(user_id='123')

        def testRecentAction(self):
            self.message_event.message = TextMessage(text='2330 RECENT')
            self.handler.handle_event(self.message_event)
            retrieve_material_information_within_date_range.assert_called_once_with('2330', date.today())

        def testHelpAction(self):
            self.message_event.message = TextMessage(text='help')
            self.handler.handle_event(self.message_event)
            reply_message.assert_called_once_with('replytoken',
                                                  '==重大訊息==\n' \
                                                  '【指令說明】\n' + \
                                                  '查詢今天重大訊息：MI [公司代號] RECENT\n' + \
                                                  '查詢近 N 天重大訊息：MI [公司代號] RECENT [N]\n' + \
                                                  '查詢指定日期後的重大訊息：MI [公司代號] RANGE [YYYYMMDD]\n' + \
                                                  '查詢指定日期範圍中的重大訊息：MI [公司代號] RANGE [YYYYMMDD] [YYYYMMDD]\n' + \
                                                  '顯示指令說明：MI HELP\n' + \
                                                  '【資料來源】\n' + \
                                                  '公開資訊觀測站：http://mops.twse.com.tw/mops/web/index')

if __name__ == '__main__':
    unittest.main()
