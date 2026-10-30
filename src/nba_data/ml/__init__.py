"""Pre-game features and models for the game predictor.

Only `team_games` touches the database, and only to read. Everything else is a
pure function over the frozen records it returns. Nothing here imports the API,
and the API never imports this package.
"""
