from peewee import Model, CharField, IntegerField, ForeignKeyField, AutoField
from db_manager.db_conf import db
from models.player import Player

class PlayerStats(Model):
    
    id_player = AutoField(primary_key=True)
    player = CharField()
    age = IntegerField()
    games = IntegerField()
    games_started = IntegerField()
    minutes_played = IntegerField()
    field_goals = IntegerField()
    field_goals_attempted = IntegerField()
    field_goals_percentage = IntegerField()
    three_point_field_goals = IntegerField()
    three_point_field_goals_attempted = IntegerField()
    three_point_field_goals_percentage = IntegerField()
    two_point_field_goals = IntegerField()
    two_point_field_goals_attempted = IntegerField()
    two_point_field_goals_percentage = IntegerField()
    effective_field_goals_percentage = IntegerField()
    free_throws = IntegerField()
    free_throws_attempted = IntegerField()
    free_throws_percentage = IntegerField()
    offensive_rebounds = IntegerField()
    defensive_rebounds = IntegerField()
    total_rebounds = IntegerField()
    assists = IntegerField()
    steals = IntegerField()
    blocks = IntegerField()
    turnovers = IntegerField()
    personal_fouls = IntegerField()
    points = IntegerField()
    id_team = ForeignKeyField(player, to_field="id_player", backref='player_stats')

    class Meta:
        database = db
        schema = 'players'
        table_name = 'player_stats'
