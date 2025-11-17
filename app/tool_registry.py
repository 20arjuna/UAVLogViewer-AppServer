"""
Tool definitions for OpenAI function calling
"""

# Tool definitions that OpenAI uses to understand what tools are available
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_available_tables",
            "description": "List all available data tables for the current flight log. Returns table names like log_<id>_ATT, log_<id>_GPS_0_, etc. Use this first to see what data is available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The file ID of the uploaded log"
                    }
                },
                "required": ["file_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_table_schema",
            "description": "Get the column names and data types for a specific table. Use this after listing tables to see what columns you can query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "The name of the table to get schema for (e.g., 'log_abc123_ATT')"
                    }
                },
                "required": ["table_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_sql",
            "description": "Execute a SQL query on the flight log database. Use this to get actual data and answer questions. Always SELECT from specific tables you've discovered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL query to execute (e.g., 'SELECT MAX(Alt) FROM log_abc123_GPS_0_')"
                    }
                },
                "required": ["sql"]
            }
        }
    }
]

