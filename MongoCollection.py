from dotenv import load_dotenv
import os
from pymongo import MongoClient
from bson.objectid import ObjectId

load_dotenv()
client = MongoClient(os.getenv('MONGODB_URI'))
db = client['heroku_z6r31tss']
collection = db['exchange_reports']


def get_exchange_reports_collection():
    return collection
