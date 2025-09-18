import os
import logging
import mysql.connector
from urllib.parse import urlparse
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_config_from_env():
    """Parses the DATABASE_URL environment variable."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable not set.")
    
    parsed_url = urlparse(db_url)
    if parsed_url.scheme != "mysql":
        raise ValueError(f"Unsupported database scheme: {parsed_url.scheme}. Only 'mysql' is supported by the init script.")

    return {
        "host": parsed_url.hostname,
        "port": parsed_url.port,
        "user": parsed_url.username,
        "password": parsed_url.password,
        "database": parsed_url.path.lstrip('/'),
    }

def initialize_database():
    """
    Connects to the database using environment variables and creates 
    the necessary tables if they don't exist.
    """
    logger.info("Attempting to initialize the database...")
    conn = None
    cursor = None
    
    try:
        db_config = get_db_config_from_env()
        
        # Retry logic for database connection
        max_retries = 10
        retry_delay = 5 # seconds
        for attempt in range(max_retries):
            try:
                conn = mysql.connector.connect(**db_config)
                logger.info("Successfully connected to the database.")
                break
            except mysql.connector.Error as e:
                logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {retry_delay}s...")
                if attempt + 1 == max_retries:
                    raise
                time.sleep(retry_delay)

        if conn and conn.is_connected():
            cursor = conn.cursor()
            
            create_table_query = """
            CREATE TABLE IF NOT EXISTS game_sessions (
                player_id VARCHAR(255) PRIMARY KEY,
                session_data TEXT,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
            """
            
            logger.info("Executing CREATE TABLE statement for game_sessions...")
            cursor.execute(create_table_query)
            conn.commit()
            logger.info("Table 'game_sessions' created or already exists.")
        else:
            logger.error("Could not establish database connection after multiple retries. Aborting initialization.")

    except (ValueError, mysql.connector.Error) as e:
        logger.error(f"An error occurred during database initialization: {e}", exc_info=True)
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
            logger.info("Database connection closed.")

if __name__ == "__main__":
    initialize_database()