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
    },
    {
        "type": "function",
        "function": {
            "name": "control_playback",
            "description": "Control the 3D flight replay playback. Use this to play, pause, or change playback speed. Speed options: speed_0.5x (slow), speed_1x (normal), speed_1.5x, speed_2x (fast), speed_5x (very fast), speed_10x (max).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["play", "pause", "speed_0.5x", "speed_1x", "speed_1.5x", "speed_2x", "speed_5x", "speed_10x"],
                        "description": "The playback action to perform"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "seek_to_timestamp",
            "description": "Jump to a specific timestamp in the flight replay. Timestamp is in milliseconds from boot (time_boot_ms).",
            "parameters": {
                "type": "object",
                "properties": {
                    "timestamp_ms": {
                        "type": "integer",
                        "description": "Timestamp in milliseconds from boot. E.g., 45000 for 45 seconds into flight."
                    }
                },
                "required": ["timestamp_ms"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "seek_to_mode",
            "description": "Jump to the first occurrence of a specific flight mode in the 3D replay. Common modes: QLAND (landing), LOITER (hold position), GUIDED (following commands), RTL (return to launch), CIRCLE.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The current file ID being analyzed"
                    },
                    "mode_name": {
                        "type": "string",
                        "description": "The flight mode name (e.g., 'QLAND', 'LOITER', 'RTL', 'CIRCLE', 'GUIDED')"
                    }
                },
                "required": ["file_id", "mode_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_plot",
            "description": "Create a time-series graph plotting one or more fields from the flight log. Use this to visualize data trends, compare values, or highlight interesting moments. The frontend will display an interactive graph. Field format: 'TABLE.COLUMN' (e.g., 'ATT.Roll', 'GPS_0_.Alt').",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The current file ID being analyzed"
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of fields to plot in format 'TABLE.COLUMN' (e.g., ['ATT.Roll', 'ATT.Pitch', 'GPS_0_.Alt']). Use table names from list_available_tables() without the 'log_xxx_' prefix."
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional descriptive title for the plot (be creative and informative!)"
                    }
                },
                "required": ["file_id", "fields"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_ui",
            "description": "Show or hide UI components (plot, chatbot, or map) to manage screen space. Use when user wants to close/hide/show/maximize different parts of the interface.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "enum": ["plot", "chatbot", "map"],
                        "description": "Which component to toggle: 'plot' (graph area), 'chatbot' (this chat interface), 'map' (3D Cesium viewer)"
                    },
                    "visible": {
                        "type": "boolean",
                        "description": "True to show the component, False to hide it"
                    }
                },
                "required": ["component", "visible"]
            }
        }
    }
]

