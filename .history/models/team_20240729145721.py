from peewee import Model, CharField, AutoField
from db_manager.db_conf import db

class Team(Model):
    id = AutoField()  # Clave primaria
    Franchise = CharField()
    Lg = CharField()
    From_Year = CharField()
    To_Year = CharField()
    Yrs = CharField()
    G = CharField()
    W = CharField()
    L = CharField()
    WL_Percent = CharField()
    Plyfs = CharField()
    Div = CharField()
    Conf = CharField()
    Champ = CharField()

    class Meta:
        database = db
        # table_name = 'teams'