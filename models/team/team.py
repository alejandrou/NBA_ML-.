from peewee import Model, CharField, AutoField, IntegerField, FloatField
from db_manager.db_conf import db

class Team(Model):
    id_team = AutoField(primary_key=True)
    team_name = CharField(unique=True)
    team_abbreviation = CharField()
    league = CharField()
    from_year = CharField()
    to_year = CharField()
    wins = IntegerField()
    losses = IntegerField()
    win_loss_percentage = FloatField()
    division = CharField()
    conference = CharField()
    championships = IntegerField(default=0)

    class Meta:
        database = db
        schema = "teams"
        table_name = "team"
