from peewee import Model, CharField, AutoField
from db_manager.db_conf import db


class BaseModel(Model):
    class Meta:
        database = db
        
class Team(BaseModel):
    team =  CharField()
    league = CharField()
    from_year = CharField()
    to_year = CharField()
    years = CharField()
    games = CharField()
    wins = CharField()
    losses = CharField()
    win_loss_percentage = CharField()
    playoffs = CharField()
    division = CharField()
    conference = CharField()
    championships = CharField()
    



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
        table_name = 'teams'
        
        