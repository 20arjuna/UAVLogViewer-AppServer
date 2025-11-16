from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import uuid
import uvicorn
import duckdb
import pandas as pd

# Create tmp directory in the repo
BASE_DIR = Path(__file__).parent.parent  # UAVLogViewer-AppServer/
TMP_DIR = BASE_DIR / "tmp" / "uav_logs"
TMP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = BASE_DIR / "tmp" / "uav_logs.duckdb"


app = FastAPI(
    title="UAV Log Viewer API",
    description="Backend API for UAV Log Viewer",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

def normalize_message_type(message_data: dict) -> pd.DataFrame:
    """
    Convert column-oriented message data to row-oriented DataFrame.
    
    Input: {"time_boot_ms": {"0": 100, "1": 200}, "Roll": {"0": 1.5, "1": 1.6}}
    Output: DataFrame with columns [time_boot_ms, Roll, ...]
    """
    if not message_data:
        return pd.DataFrame()
    
    # Convert each attribute from {index: value} to a list
    data = {}
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
        
        # Clean table name (replace brackets and hyphens, add prefix to avoid starting with number)
        table_name = f"log_{file_id}_{msg_type}".replace("[", "_").replace("]", "_").replace("-", "_")
        
        # Store in DuckDB
        conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        
        print(f"✅ Created table {table_name} with {len(df)} rows")
    
    conn.close()


# -- Routes --
@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/upload")
def save_data(data: dict = Body(...)):
    file_id = str(uuid.uuid4())
    
    # Normalize and store in DuckDB
    try:
        ingest_and_normalize(data, file_id)
        print(f"✅ Ingested and normalized log with file_id: {file_id}")
    except Exception as e:
        print(f"❌ Error normalizing data: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    
    return {
        "file_id": file_id, 
        "status": "normalized"
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)