import os
from mongoengine import *
connect(host=os.getenv('MONGODB_URI') + '/' + os.getenv('MONGODB_DATABASE'))


class MaterialInformation(Document):
    id = StringField(required=True, primary_key=True)
    spoken_date = DateField(required=True)
    fact_date = DateField(required=True)
    title = StringField(required=True)
    content = StringField(required=True)
