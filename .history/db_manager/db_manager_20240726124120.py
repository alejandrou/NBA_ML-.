from models.team import team
import db_connection
from playhouse.shortcuts import dict_to_model

class DatabaseManager:
    def __init__(self):
        pass



#clase intermedia que se encarga de sacar datos de scrap y meterlos en base de datos
#habria que hacer el import del scrap script y el de la clase team para hacer la insercion, buscar la manera a lo mejor de poder hacerlo con todas las clases
#futuras aunque lo dudo que se pueda hacer, pero por intentarlo