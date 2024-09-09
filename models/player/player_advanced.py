from peewee import Model, CharField, IntegerField, ForeignKeyField, AutoField
from db_manager.db_conf import db
from models.player.player import Player

class PlayerAdvancedStats(Model):
    
    id_player_stat_advanced = AutoField(primary_key=True)
    id_player = ForeignKeyField(Player, to_field="id_player")
    rk = CharField()
    player = CharField()
    age = IntegerField()
    games = IntegerField()
    minutes_played = IntegerField()
    player_effiencey_rating = CharField()
    true_shooting_percentage = CharField()
    three_point_attempt_rate = CharField()
    free_throw_attempt_rate = CharField()
    offensive_rebound_percentage = CharField()
    defensive_rebound_percentage = CharField()
    total_rebound_percentage = CharField()
    assist_percentage = CharField()
    steal_percentage = CharField()
    block_percentage = CharField()
    turnover_percentage = CharField()
    usage_percentage = CharField()
    offensive_win_shares = CharField()
    defensive_win_shares = CharField()
    win_shares = CharField()
    win_shares_per_48_minutes = CharField()
    offensive_box_plus_minus = CharField()
    defensive_box_plus_minus = CharField()
    box_plus_minus = CharField()
    value_over_replacement_player = CharField(null = True)
    
    class Meta:
        database = db
        schema = 'players'
        table_name = 'player_advanced'
