import os
from mongoengine import *

connect(host=os.getenv('MONGODB_URI') + '/' + os.getenv('MONGODB_DATABASE'))

__all__ = (
    'NotificationFlag', 'Notification', 'ExchangeNotification',
    'MaterialInformation'
)


class NotificationFlag(EmbeddedDocument):
    rate = DecimalField()
    notified = BooleanField()


class Notification(EmbeddedDocument):
    currency = StringField(required=True, primary_key=True)
    sell = EmbeddedDocumentField(NotificationFlag)
    buy = EmbeddedDocumentField(NotificationFlag)


class ExchangeNotification(Document):
    source = StringField(required=True, primary_key=True)
    notify_rates = EmbeddedDocumentListField(Notification)


class MaterialInformation(Document):
    id = StringField(required=True, primary_key=True)
    company_code = IntField(required=True)
    spoken_at = DateTimeField(required=True)
    speaker = StringField()
    speaker_title = StringField()
    speaker_phone = StringField()
    terms = StringField()
    fact_date = DateField(required=True)
    title = StringField(required=True)
    content = StringField(required=True)

    @property
    def spoken_roc_date(self):
        spoken_date_str = self.spoken_at.strftime('%Y/%m/%d')
        return spoken_date_str.replace(spoken_date_str[:4],
                                       str(int(spoken_date_str[:4]) - 1911))

    @property
    def fact_roc_date(self):
        fact_date_str = self.fact_date.strftime('%Y/%m/%d')
        return fact_date_str.replace(fact_date_str[:4],
                                                  str(int(fact_date_str[:4]) - 1911))

    def to_line_message(self):
        spoken_date_str = self.spoken_at.strftime('%Y/%m/%d')
        spoken_roc_date_str = spoken_date_str.replace(spoken_date_str[:4],
                                                      str(int(spoken_date_str[:4]) - 1911))

        fact_date_str = self.fact_date.strftime('%Y/%m/%d')
        fact_roc_date_str = fact_date_str.replace(fact_date_str[:4],
                                                  str(int(fact_date_str[:4]) - 1911))

        return f'【發言日期】{spoken_roc_date_str}' \
                   f'\n【事實發生日】{fact_roc_date_str}' \
                   f'\n【主旨】\n{self.title}' \
                   f'\n【說明】\n{self.content}'[:2000]
