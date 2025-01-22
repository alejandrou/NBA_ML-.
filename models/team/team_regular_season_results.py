from peewee import Model, CharField, AutoField, ForeignKeyField, IntegerField
from db_manager.db_conf import db
from models.team.team import Team
from models.team.team_season import TeamSeason

class TeamRegularSeasonResults(Model):
    id_team_regular_season_results = AutoField(primary_key=True)
    id_team = ForeignKeyField(TeamSeason, to_field="id_team", backref="results")
    opp_team = ForeignKeyField(Team, to_field="id_team", backref="opponent_games")
    game = IntegerField(null=True)
    date_game = CharField()
    game_start_time = CharField()
    game_result = CharField()
    overtimes = CharField(null=True)
    wins = IntegerField(null=True)
    losses = IntegerField(null=True)
    game_streak = CharField()
    game_location = CharField(null=True)
    pts = IntegerField()
    opp_pts = IntegerField()
    attendance = CharField(null=True)
    game_duration = CharField()
    game_remarks = CharField(null=True)
    year = IntegerField()

    class Meta:
        database = db
        schema = 'teams'
        table_name = 'team_regular_season_results'
