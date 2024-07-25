from models.team import team
import db_connection
from playhouse.shortcuts import dict_to_model

class DatabaseManager:
    def __init__(self):
        pass

    def insert_teams(self, df):
        with db_connection.db.atomic():
            for index, row in df.iterrows():
                team_data = {
                    'Franchise': row['Franchise'],
                    'Lg': row['Lg'],
                    'From_Year': row['From'],
                    'To_Year': row['To'],
                    'Yrs': row['Yrs'],
                    'G': row['G'],
                    'W': row['W'],
                    'L': row['L'],
                    'WL_Percent': row['W/L%'],
                    'Plyfs': row['Plyfs'],
                    'Div': row['Div'],
                    'Conf': row['Conf'],
                    'Champ': row['Champ']
                }
                team_instance = dict_to_model(team, team_data)
                team_instance.save()


#clase intermedia que se encarga de sacar datos de scrap y meterlos en base de datos
#habria que hacer el import del scrap script y el de la clase team para hacer la insercion, buscar la manera a lo mejor de poder hacerlo con todas las clases
#futuras aunque lo dudo que se pueda hacer, pero por intentarlo
