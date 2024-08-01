from peewee import Model, CharField, IntegerField, ForeignKeyField
from db_manager.db_conf import db
import models.team as team

class Player(Model):
        
        id_player = IntegerField(primary_key=True)
        player_name = CharField()
        player_position = CharField()
        player_height = CharField()
        player_weight = CharField()
        player_birth_date = CharField()
        player_experience = CharField()
        player_college = CharField()
        id_team = ForeignKeyField(team, to_field="team_id")()
        
        class Meta:
            database = db