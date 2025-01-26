from peewee import Model, CharField, FloatField, IntegerField, ForeignKeyField, AutoField
from db_manager.db_conf import db
from models.player.player import Player

class PlayerAdvancedStats(Model):
    
    id_player_stat_advanced = AutoField(primary_key=True)
    id_player = ForeignKeyField(Player, to_field="id_player")
    rk = CharField()
    player = CharField()
    games = IntegerField()
    minutes_played = IntegerField()
    player_effiencey_rating = FloatField()
    true_shooting_percentage = CharField(null=True)
    three_point_attempt_rate = CharField(null=True)
    free_throw_attempt_rate = CharField(null=True)
    offensive_rebound_percentage = CharField(null=True)
    defensive_rebound_percentage = CharField(null=True)
    total_rebound_percentage =CharField(null=True)
    assist_percentage = CharField(null=True)
    steal_percentage =  CharField(null=True)
    block_percentage =  CharField(null=True)
    turnover_percentage = CharField(null=True)
    usage_percentage = CharField(null=True)
    offensive_win_shares = FloatField()
    defensive_win_shares = FloatField()
    win_shares = FloatField()
    win_shares_per_48_minutes = FloatField()
    offensive_box_plus_minus = FloatField()
    defensive_box_plus_minus = FloatField()
    box_plus_minus = FloatField()
    value_over_replacement_player = FloatField(null=True)
    
    class Meta:
        database = db
        schema = 'players'
        table_name = 'player_advanced'
