from peewee import Model, CharField, ForeignKeyField, AutoField
from db_manager.db_conf import db
from models.team import Team

class Player(Model):
        
        id_player = AutoField(primary_key=True)
        number_player = CharField()
        player_name = CharField()
        player_position = CharField()
        player_height = CharField()
        player_weight = CharField()
        player_birth_date = CharField()
        player_experience = CharField()
        player_college = CharField(null=True)
        player_team = CharField(null=True)
        player_year_in_team = CharField()
        id_team = ForeignKeyField(Team, to_field="team_id", backref='players')
        
        class Meta:
            database = db