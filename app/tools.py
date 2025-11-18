"""
Tool functions for the AI agent to interact with UAV log data
"""
import duckdb
from config import DB_PATH



def list_available_tables(file_id: str) -> list:
    """
    List all available tables for a given file_id.
    Returns list of table names that belong to this file_id.
    """
    conn = duckdb.connect(str(DB_PATH))
    
    # Clean file_id for matching (replace hyphens with underscores)
    clean_file_id = file_id.replace("-", "_")
    
    # Get all tables that start with log_{file_id}_
    query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'main' 
        AND table_name LIKE ?
    """
    
    tables = conn.execute(query, [f"log_{clean_file_id}_%"]).fetchall()
    conn.close()
    
    # Extract just the table names from tuples
    table_list = [table[0] for table in tables]
    
    return table_list


def get_table_schema(table_name: str) -> dict:
    """
    Get the schema (column names and types) for a specific table.
    Returns dict mapping column names to their data types.
    
    Example:
        {"time_boot_ms": "BIGINT", "Roll": "DOUBLE", "Pitch": "DOUBLE"}
    """
    conn = duckdb.connect(str(DB_PATH))
    
    try:
        # Use DuckDB's DESCRIBE command to get schema info
        result = conn.execute(f'DESCRIBE "{table_name}"').fetchall()
        
        # DESCRIBE returns: (column_name, column_type, null, key, default, extra)
        # We want column_name (index 0) and column_type (index 1)
        schema = {row[0]: row[1] for row in result}
        
        conn.close()
        return schema
    except Exception as e:
        conn.close()
        raise Exception(f"Error getting schema for table '{table_name}': {str(e)}")


def query_sql(sql: str) -> dict:
    """
    Execute a SQL query on the UAV log database.
    Returns structured result with success status, data, and metadata.
    
    Args:
        sql: SQL query string to execute (SELECT queries recommended)
    
    Returns:
        {
            "success": True/False,
            "data": [...] or None,
            "columns": [...] or None,
            "row_count": int,
            "error": str (only if success=False)
        }
    
    Example:
        query_sql("SELECT MAX(Alt) as max_altitude FROM log_abc_GPS_0_")
        # Returns: {
        #     "success": True,
        #     "data": [[342.5]],
        #     "columns": ["max_altitude"],
        #     "row_count": 1
        # }
    """
    conn = duckdb.connect(str(DB_PATH))
    
    try:
        # Execute the query
        result = conn.execute(sql)
        
        # Fetch all results
        data = result.fetchall()
        
        # Get column names
        columns = [desc[0] for desc in result.description] if result.description else []
        
        conn.close()
        
        return {
            "success": True,
            "data": data,
            "columns": columns,
            "row_count": len(data)
        }
    except Exception as e:
        conn.close()
        return {
            "success": False,
            "data": None,
            "columns": None,
            "row_count": 0,
            "error": str(e),
            "sql": sql  # Include the SQL that failed for debugging
        }


# =============================================================================
# FLIGHT CONTROL TOOLS - Control the 3D viewer UI
# =============================================================================

def control_playback(action: str) -> dict:
    """
    Control 3D flight replay playback.
    
    Args:
        action: One of:
            - "play": Start playing forward
            - "pause": Pause playback
            - "speed_0.5x": Half speed
            - "speed_1x": Normal speed (default)
            - "speed_1.5x": 1.5x speed
            - "speed_2x": 2x speed
            - "speed_5x": 5x speed
            - "speed_10x": 10x speed (maximum)
    
    Returns:
        Command dict for frontend to execute
    
    Examples:
        control_playback("pause")
        control_playback("play")
        control_playback("speed_2x")
    """
    valid_actions = ["play", "pause", "speed_0.5x", "speed_1x", "speed_1.5x", 
                     "speed_2x", "speed_5x", "speed_10x"]
    
    if action not in valid_actions:
        return {
            "error": f"Invalid action '{action}'. Valid actions: {', '.join(valid_actions)}"
        }
    
    return {
        "type": "command",
        "action": "control_playback",
        "params": {"action": action}
    }


def seek_to_timestamp(timestamp_ms: int) -> dict:
    """
    Jump to a specific timestamp in the flight.
    
    Args:
        timestamp_ms: Time in milliseconds from boot (from time_boot_ms column)
    
    Returns:
        Command dict for frontend to execute
    
    Example:
        seek_to_timestamp(45000)  # Jump to 45 seconds into flight
    """
    if timestamp_ms < 0:
        return {"error": "Timestamp cannot be negative"}
    
    return {
        "type": "command",
        "action": "seek_to_timestamp",
        "params": {"timestamp": timestamp_ms}
    }


def seek_to_mode(file_id: str, mode_name: str) -> dict:
    """
    Jump to the first occurrence of a specific flight mode.
    
    Args:
        file_id: The current file being analyzed
        mode_name: Flight mode name (e.g., "QLAND", "LOITER", "CIRCLE", "GUIDED", "RTL")
    
    Returns:
        Command dict for frontend, or error if mode not found
    
    Example:
        seek_to_mode(file_id, "QLAND")  # Jump to landing phase
    """
    conn = duckdb.connect(str(DB_PATH))
    
    # Clean file_id for table name
    clean_file_id = file_id.replace("-", "_")
    
    # Common ArduPilot mode mappings (mode number -> name)
    mode_map = {
        "STABILIZE": 0, "ACRO": 1, "ALT_HOLD": 2, "AUTO": 3, "GUIDED": 4,
        "LOITER": 5, "RTL": 6, "CIRCLE": 7, "LAND": 9,
        "QSTABILIZE": 17, "QHOVER": 18, "QLOITER": 19, "QLAND": 20, "QRTL": 21
    }
    
    mode_name_upper = mode_name.upper()
    mode_number = mode_map.get(mode_name_upper)
    
    if mode_number is None:
        conn.close()
        return {
            "error": f"Unknown mode '{mode_name}'. Known modes: {', '.join(mode_map.keys())}"
        }
    
    try:
        # Try to find HEARTBEAT table first
        table_name = f"log_{clean_file_id}_HEARTBEAT"
        result = conn.execute(f"""
            SELECT time_boot_ms 
            FROM "{table_name}"
            WHERE custom_mode = {mode_number}
            ORDER BY time_boot_ms
            LIMIT 1
        """).fetchone()
        
        conn.close()
        
        if result:
            timestamp = result[0]
            return seek_to_timestamp(int(timestamp))
        else:
            return {"error": f"Mode '{mode_name}' not found in this flight"}
            
    except Exception as e:
        conn.close()
        return {"error": f"Could not search for mode: {str(e)}"}

