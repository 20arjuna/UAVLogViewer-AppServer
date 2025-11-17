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

