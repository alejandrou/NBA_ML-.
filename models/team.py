from peewee import Model, CharField, AutoField

class Team(Model):
    id = AutoField()  # Clave primaria
    Franchise = CharField()
    Lg = CharField()
    From_Year = CharField()
    To_Year = CharField()
    Yrs = CharField()
    G = CharField()
    W = CharField()
    L = CharField()
    WL_Percent = CharField()
    Plyfs = CharField()
    Div = CharField()
    Conf = CharField()
    Champ = CharField()

        
#Sería separar conexion de base de datos e insercion de base de datos de aqui, solo colocar la clase team como una especie de DTO
