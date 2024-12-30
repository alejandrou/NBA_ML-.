from db_manager.db_conf import db

class DBManager:
    
    @staticmethod
    def connect_db():
        db.connect()

    @staticmethod
    def close_db():
        db.close()

    @staticmethod
    def create_tables(table):
        db.create_tables([table])

    @staticmethod
    def drop_tables(table):
        db.drop_tables([table])

    @staticmethod
    def create_schemas(schema_name):
        db.execute_sql(f'CREATE SCHEMA IF NOT EXISTS {schema_name};')

    @staticmethod
    def drop_schemas(schema_name):
        db.execute_sql(f'DROP SCHEMA IF EXISTS {schema_name} CASCADE;')

    @staticmethod
    def table_exists(table_name):
        return db.table_exists(table_name)