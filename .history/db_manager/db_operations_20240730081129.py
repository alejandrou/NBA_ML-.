from db_manager.db_conf import db

class DBOperations():
    
        def __init__(self):
            pass
        
        def connect_db(self):
            db.connect()
        
        def close_db(self):
            db.close()
        
        