def get_win_loss_win_loss_percentage(team_regular_season_results, team_name):
    for team, years_data in team_regular_season_results.items():
        if team == team_name:  # Match the team name
            for year, stats in years_data.items():
                if stats:
                    last_game = stats[-1]
                    wins = int(last_game.get('wins', 0))
                    losses = int(last_game.get('losses', 0))
                    games_played = wins + losses
                    win_loss_percentage = round((wins / games_played) * 100, 2) if games_played > 0 else 0.0
                    return wins, losses, win_loss_percentage
    return 0, 0, 0.0  # Default if no data found