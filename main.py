from db_manager.db_manager import DBManager
from db_manager.team_operations import TeamOperations
from db_manager.player_operations import PlayerOperations

def main():
    data_manager = DBManager()
    player_operations = PlayerOperations()
    team_operations = TeamOperations()
    
    print("Connecting to database...")
    data_manager.connect_db()

    print("Creating schemas...")
    data_manager.create_schemas('teams')
    data_manager.create_schemas('players')
    
    print("Creating team table and inserting data...")
    team_operations.scrape_and_save_teams()
    team_operations.scrape_and_save_teams_season_results()

    ## HAY QUE AVERIGUAR PORQUE LO HACE DE UNO EN UNO, LO QUE MOLABA ES QUE COGIERA CON EL ASYNC 20 REQUESTS CADA MINUTO Y QUE FUERA INSERTANDO
    ## COMO POR BATCHES

    # Voy a limpiar proyecto de asincronia, creo que para lo que queremos hacer no funcionara a menos que se quiera hacer por batches como puse en su dia
    # como no se entiende del todo lo ideal es limpiarlo todo y volver a hacerlo para un caso solo y ver como funciona bien. REFACTOR TIIIME
    
    # print("Creating player table and inserting data...")
    # await player_operations.scrape_and_save_players_roster()
    # await player_operations.scrape_and_save_players_totals()
    # await player_operations.scrape_and_save_players_advanced()

    # print("Dropping schemas...")
    # data_manager.drop_schemas('teams')
    # data_manager.drop_schemas('players')
    
    print("Closing database connection...")
    data_manager.close_db()

if __name__ == "__main__":
    main()