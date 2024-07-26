from peewee import Model, CharField, AutoField

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
