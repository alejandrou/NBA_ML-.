from peewee import Model, CharField, IntegerField
from db_manager.db_conf import db

class Season(Model):
    
    id_season = IntegerField(primary_key=True)
    season_date = CharField()
    season_description = CharField()
    
    class Meta:
        database = db