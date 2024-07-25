from peewee import PostgresqlDatabase



db = PostgresqlDatabase(
    'mydatabase',
    user='myuser',
    password='mysecretpassword',
    host='tu_host',
    port='puerto'
)

def connect():
    db.connect()

def close():
    db.close()

def create_tables(tables):
    db.create_tables(tables)