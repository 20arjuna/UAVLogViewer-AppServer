"""
Data ingestion and normalization functions for UAV logs
"""
import duckdb
import pandas as pd
from config import DB_PATH



def normalize_message_type(message_data: dict) -> pd.DataFrame:
    """
    Convert column-oriented message data to row-oriented DataFrame.
    Handles fields with different lengths by padding with None.
    
    Input: {"time_boot_ms": {"0": 100, "1": 200}, "Roll": {"0": 1.5, "1": 1.6}}
    Output: DataFrame with columns [time_boot_ms, Roll, ...]
    """
    if not message_data:
        return pd.DataFrame()
    
    # Convert each attribute from {index: value} to a list
    data = {}
    max_length = 0
    
    for field_name, field_values in message_data.items():
        # Handle both dict format {"0": val, "1": val} and list format [val1, val2]
        if isinstance(field_values, dict):
            sorted_items = sorted(field_values.items(), key=lambda x: int(x[0]))
            data[field_name] = [v for k, v in sorted_items]
        elif isinstance(field_values, list):
            data[field_name] = field_values
        else:
            # Skip non-dict, non-list values
            continue
        
        # Track the longest array
        max_length = max(max_length, len(data[field_name]))
    
    # Pad all arrays to the same length with None
    for field_name in data:
        current_length = len(data[field_name])
        if current_length < max_length:
            # Pad with None
            data[field_name].extend([None] * (max_length - current_length))
            print(f"⚠️  Padded {field_name} from {current_length} to {max_length} values")
    
    return pd.DataFrame(data)


def ingest_and_normalize(raw_data: dict, file_id: str):
    """
    Normalize the raw JSON and store in DuckDB.
    Creates one table per message type.
    """
    conn = duckdb.connect(str(DB_PATH))
    
    messages = raw_data.get("messages", {})
    
    # Process each message type
    for msg_type, msg_data in messages.items():
        if msg_type == "FILE":  # Skip metadata
            continue
            
        # Normalize to DataFrame
        df = normalize_message_type(msg_data)
        
        if df.empty:
            continue
        
        # Clean up data types for DuckDB compatibility
        for col in df.columns:
            if df[col].dtype == 'bool':
                # Convert boolean columns to integers
                df[col] = df[col].astype('Int64')
            elif df[col].dtype == 'object':
                # Check first non-null value to determine handling
                first_val = df[col].dropna().iloc[0] if len(df[col].dropna()) > 0 else None
                
                if isinstance(first_val, (list, tuple)):
                    # Convert array/list columns to strings
                    df[col] = df[col].astype(str)
                elif isinstance(first_val, bool):
                    # Convert top-level booleans to integers
                    df[col] = df[col].replace({True: 1, False: 0})
        
        # Clean table name (replace brackets and hyphens, add prefix to avoid starting with number)
        table_name = f"log_{file_id}_{msg_type}".replace("[", "_").replace("]", "_").replace("-", "_")
        
        # Store in DuckDB
        conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        
        print(f"✅ Created table {table_name} with {len(df)} rows")
    
    conn.close()

