import asyncio
import json
import logging
import time
from .websocket_manager import manager as websocket_manager
from .live_system import live_manager
from . import security
from . import db

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Database Interaction Functions ---

async def get_session(player_id: str) -> dict | None:
    """Gets the session object from the database."""
    conn = db.get_db_connection()
    if not conn:
        return None
    
    try:
        # For MySQL, we want dictionary cursors. For SQLite, row_factory is set in db.py
        is_mysql = 'mysql' in str(type(conn)).lower()
        cursor = conn.cursor(dictionary=True) if is_mysql else conn.cursor()

        # MySQL uses %s, SQLite uses ?. We assume MySQL for now as per the .env file.
        cursor.execute("SELECT session_data FROM game_sessions WHERE player_id = %s", (player_id,))
        row = cursor.fetchone()
        
        if row:
            session_data = row['session_data'] # type: ignore
            if session_data:
                return json.loads(session_data)
        return None
    except Exception as e:
        logger.error(f"Failed to get session for player {player_id}: {e}")
        return None
    finally:
        if conn and hasattr(conn, 'is_connected') and conn.is_connected():
            cursor.close()
            conn.close()
        elif conn: # For sqlite3
             conn.close()


async def save_session(player_id: str, session_data: dict):
    """
    Saves the entire session data for a player to the database and pushes it to their WebSocket.
    """
    conn = db.get_db_connection()
    if not conn:
        return

    try:
        session_data["last_modified"] = time.time()
        session_str = json.dumps(session_data, ensure_ascii=False)
        cursor = conn.cursor()

        # Use MySQL's INSERT ... ON DUPLICATE KEY UPDATE for efficiency
        query = """
        INSERT INTO game_sessions (player_id, session_data)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE session_data = VALUES(session_data);
        """
        cursor.execute(query, (player_id, session_str))
        conn.commit()

        tasks = [
            websocket_manager.send_json_to_player(
                player_id, {"type": "full_state", "data": session_data}
            ),
            live_manager.broadcast_state_update(player_id, session_data)
        ]
        asyncio.gather(*tasks)

    except Exception as e:
        logger.error(f"Failed to save session for player {player_id}: {e}")
    finally:
        if conn and hasattr(conn, 'is_connected') and conn.is_connected():
            cursor.close()
            conn.close()
        elif conn:
             conn.close()

async def create_or_get_session(player_id: str) -> dict:
    """
    Retrieves a session from the DB. If it doesn't exist, creates an empty one.
    """
    session = await get_session(player_id)
    if session is None:
        session = {}
        await save_session(player_id, session)
    return session

async def get_last_n_inputs(player_id: str, n: int) -> list[str]:
    """Get the last N player inputs for a session."""
    session = await get_session(player_id)
    if not session: return []
    history = session.get("internal_history", [])
    return [item["content"] for item in history if item.get("role") == "user"][-n:]

def get_most_recent_sessions(limit: int = 10) -> list[dict]:
    """Gets the most recently active sessions from the database."""
    conn = db.get_db_connection()
    if not conn: return []

    try:
        is_mysql = 'mysql' in str(type(conn)).lower()
        cursor = conn.cursor(dictionary=True) if is_mysql else conn.cursor()
        
        query = "SELECT player_id, session_data FROM game_sessions ORDER BY last_modified DESC LIMIT %s"
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()

        results = []
        for row in rows:
            player_id = str(row['player_id']) # type: ignore
            session_data = json.loads(str(row['session_data'])) # type: ignore
            
            encrypted_id = security.encrypt_player_id(player_id)
            display_name = f"{player_id[0]}...{player_id[-1]}" if len(player_id) > 2 else player_id
            
            results.append({
                "player_id": encrypted_id,
                "display_name": display_name,
                "last_modified": session_data.get("last_modified", 0)
            })
        return results
    except Exception as e:
        logger.error(f"Failed to get most recent sessions: {e}")
        return []
    finally:
        if conn and hasattr(conn, 'is_connected') and conn.is_connected():
            cursor.close()
            conn.close()
        elif conn:
             conn.close()

async def clear_session(player_id: str):
    """Clears a player's session."""
    await save_session(player_id, {})
    logger.info(f"Session for player {player_id} has been cleared.")

async def flag_player_for_punishment(player_id: str, level: str, reason: str):
    """Flags a player's session for punishment."""
    session = await get_session(player_id)
    if not session:
        logger.warning(f"Attempted to flag non-existent session for player {player_id}")
        return

    session["pending_punishment"] = {"level": level, "reason": reason}
    await save_session(player_id, session)
    logger.info(f"Player {player_id} flagged for {level} punishment. Reason: {reason}")