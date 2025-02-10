from peewee import Model, CharField, AutoField, IntegerField, FloatField
from db_manager.db_conf import db

class Team(Model):
    id_team = AutoField(primary_key=True)
    team_name = CharField(unique=True)
    team_abbreviation = CharField()
    league = CharField(null=True)
    from_year = CharField(null=True)
    to_year = CharField(null=True)
    wins = IntegerField(null=True)
    losses = IntegerField(null=True)
    win_loss_percentage = FloatField(null=True)
    division = CharField(null=True)
    conference = CharField(null=True)
    championships = IntegerField(null=True)

    class Meta:
        database = db
        schema = "teams"
        table_name = "team"
