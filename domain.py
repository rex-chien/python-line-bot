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
    spoken_date = DateField(required=True)
    fact_date = DateField(required=True)
    title = StringField(required=True)
    content = StringField(required=True)
