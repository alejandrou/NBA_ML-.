import os

from peewee import PostgresqlDatabase

db = PostgresqlDatabase(
    os.getenv("POSTGRES_DB", "nba"),
    user=os.getenv("POSTGRES_USER", "nba"),
    password=os.getenv("POSTGRES_PASSWORD", "nba"),
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
)
