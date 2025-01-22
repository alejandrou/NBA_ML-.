from peewee import Model, CharField, FloatField,IntegerField, ForeignKeyField, AutoField
from db_manager.db_conf import db
from models.player.player import Player

class PlayerStats(Model):
    
    id_player_stat = AutoField(primary_key=True)
    id_player = ForeignKeyField(Player, to_field="id_player")
    player = CharField()
    age = IntegerField()
    games = IntegerField()
    games_started = IntegerField()
    minutes_played = IntegerField()
    field_goals = IntegerField()
    field_goals_attempted = IntegerField()
    field_goals_percentage = FloatField()
    three_point_field_goals = IntegerField()
    three_point_field_goals_attempted = IntegerField()
    three_point_field_goals_percentage = FloatField()
    two_point_field_goals = IntegerField()
    two_point_field_goals_attempted = IntegerField()
    two_point_field_goals_percentage = FloatField()
    effective_field_goals_percentage = FloatField()
    free_throws = IntegerField()
    free_throws_attempted = IntegerField()
    free_throws_percentage = FloatField()
    offensive_rebounds = IntegerField()
    defensive_rebounds = IntegerField()
    total_rebounds = IntegerField()
    assists = IntegerField()
    steals = IntegerField()
    blocks = IntegerField()
    turnovers = IntegerField()
    personal_fouls = IntegerField()
    points = IntegerField()
    

    class Meta:
        database = db
        schema = 'players'
        table_name = 'player_stats'
