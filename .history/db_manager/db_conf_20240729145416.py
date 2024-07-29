from peewee import PostgresqlDatabase

db = PostgresqlDatabase(
    'mydatabase',  # Nombre de la base de datos
    user='myuser',  # Usuario de la base de datos
    password='mysecretpassword',  # Contraseña del usuario
    host='localhost',  # Host donde corre PostgreSQL
    port=5432  # Puerto donde escucha PostgreSQL

)