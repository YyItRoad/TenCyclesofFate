import sqlite3
import logging
import mysql.connector
from urllib.parse import urlparse
from mysql.connector import pooling
from .config import settings

logger = logging.getLogger(__name__)

# --- Global Connection Pool ---
db_pool = None

def initialize_db_pool():
    """Initializes the database connection pool based on the DATABASE_URL."""
    global db_pool
    try:
        db_url = settings.DATABASE_URL
        parsed_url = urlparse(db_url)

        if parsed_url.scheme == "mysql":
            pool_config = {
                "host": parsed_url.hostname,
                "port": parsed_url.port,
                "user": parsed_url.username,
                "password": parsed_url.password,
                "database": parsed_url.path.lstrip('/'),
                "pool_name": "game_pool",
                "pool_size": 5, # Start with a pool of 5 connections
            }
            db_pool = pooling.MySQLConnectionPool(**pool_config)
            logger.info(f"MySQL connection pool '{db_pool.pool_name}' initialized.")
        # SQLite does not require a traditional pool in the same way for this app's structure
    except mysql.connector.Error as e:
        logger.error(f"Failed to initialize MySQL connection pool: {e}", exc_info=True)
        db_pool = None

def get_db_connection():
    """Gets a connection from the pool or creates a new one for SQLite."""
    try:
        db_url = settings.DATABASE_URL
        parsed_url = urlparse(db_url)

        if parsed_url.scheme == "sqlite":
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn # SQLite connections are lightweight, direct creation is fine
        
        elif parsed_url.scheme == "mysql":
            if db_pool is None:
                logger.error("MySQL pool is not initialized. Cannot get connection.")
                return None
            # This gets a connection from the already created pool
            return db_pool.get_connection()
            
        else:
            logger.error(f"Unsupported database scheme: {parsed_url.scheme}")
            return None
            
    except (sqlite3.Error, mysql.connector.Error) as e:
        logger.error(f"Database connection failed: {e}", exc_info=True)
        return None