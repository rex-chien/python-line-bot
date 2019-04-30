from unittest.mock import MagicMock, patch
import pytest
import datetime
from linebot.models import TextMessage

fake_today = datetime.date(2019, 3, 4)


@pytest.fixture(scope='module', autouse=True)
def mock_today():
    _standard_date = datetime.date

    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return cls(fake_today.year, fake_today.month, fake_today.day)

    datetime.date = FakeDate

    yield

    datetime.date = _standard_date


@pytest.fixture(scope='class')
def setup_mops_tests(request):
    from line_event_handlers import MopsEventHandler

    request.cls.retrieve_material_information_within_date_range = patch(
        'line_event_handlers.mops_event_handler.retrieve_material_information_within_date_range',
        MagicMock()).start()

    request.cls.handler = MopsEventHandler()

    yield

    patch.stopall()


@pytest.mark.usefixtures('setup_handler_tests', 'setup_mops_tests')
class TestMopsMessageHandler:
    def test_help_action(self):
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

    def test_recent_action(self):
        self.given_command_should_retrieve_with_CompanyCode_BeginDate_EndDate(
            command='2330 RECENT',
            company_code='2330',
            begin_date=fake_today
        )

    def test_recent_action_7(self):
        self.given_command_should_retrieve_with_CompanyCode_BeginDate_EndDate(
            command='2330 RECENT 7',
            company_code='2330',
            begin_date=fake_today - datetime.timedelta(days=6)
        )

    def test_range_action_20190101_to_20190304(self):
        self.given_command_should_retrieve_with_CompanyCode_BeginDate_EndDate(
            command='2330 RANGE 20190101 20190304',
            company_code='2330',
            begin_date=datetime.date(2019, 1, 1),
            end_date=datetime.date(2019, 3, 4)
        )

    def given_command_should_retrieve_with_CompanyCode_BeginDate_EndDate(
            self, command, company_code, begin_date, end_date=None):
        self.message_event.message = TextMessage(text=command)
        self.handler.handle_event(self.message_event)

        if end_date:
            self.retrieve_material_information_within_date_range \
                .assert_called_once_with(company_code, begin_date, end_date)
        else:
            self.retrieve_material_information_within_date_range \
                .assert_called_once_with(company_code, begin_date)

        self.retrieve_material_information_within_date_range.reset_mock()
