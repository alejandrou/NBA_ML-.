from peewee import Model, CharField, AutoField, IntegerField, ForeignKeyField, FloatField, BooleanField
from db_manager.db_conf import db
from models.team.team import Team

'''
    Esta tabla representará una relación entre un equipo (Team) y una temporada específica.
'''
class TeamSeason(Model):
    id_team_season = AutoField(primary_key=True)
    id_team = ForeignKeyField(Team, to_field="id_team", backref="seasons")
    year = IntegerField() 
    wins = IntegerField()
    losses = IntegerField()
    win_loss_percentage = FloatField()

    class Meta:
        database = db
        schema = 'teams'
        table_name = 'team_season'
        # indexes = (
        #     (('id_team', 'year'), True),  # Índice único para evitar duplicados por equipo y año
        # )
