from peewee import Model, CharField, PostgresqlDatabase
from db_connection import db

class Team(Model):
    Franchise = CharField()
    Lg = CharField()
    From_Year = CharField()  # 'From' es una palabra reservada en Python, por lo que se utiliza 'From_Year'
    To_Year = CharField()    # 'To' es una palabra reservada en Python, por lo que se utiliza 'To_Year'
    Yrs = CharField()
    G = CharField()
    W = CharField()
    L = CharField()
    WL_Percent = CharField()  # 'W/L%' contiene caracteres especiales, por lo que se usa 'WL_Percent'
    Plyfs = CharField()
    Div = CharField()
    Conf = CharField()
    Champ = CharField()


    class Meta:
        database = db
        table_name = 'teams'
        

db.connect()
db.create_tables([Team])

#Sería separar conexion de base de datos e insercion de base de datos de aqui, solo colocar la clase team como una especie de DTO
#Habria que ver como quitar el playhouse, primero ver que es y luego ver si desde el df se puede hacer directamente a la base de datos