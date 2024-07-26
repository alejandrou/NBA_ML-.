from scrap.scrap_team import TeamScraper
from models.team import Team
from db_manager.db_manager import initialize_db

def main():
    scraper = TeamScraper()
    df = scraper.get_team_table()

    # Conectar y crear tablas si es necesario
    initialize_db()
    
    # Guardar datos en la base de datos
    for index, row in df.iterrows():
        Team.create(
            name=row['Team'],
            # Agregar otros campos necesarios mapeados desde el DataFrame
        )

if __name__ == "__main__":
    main()
