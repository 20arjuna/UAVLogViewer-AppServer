from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import uuid
import uvicorn
import duckdb

# Import from our modules
from config import DB_PATH
from ingestion import ingest_and_normalize
from agent import run_agent

# Global state - tracks the currently active file_id
current_file_id = None


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


# -- Routes --
@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/reset")
def reset_database():
    """
    Clear all tables from DuckDB and reset the current file_id.
    Useful for starting fresh.
    """
    global current_file_id
    
    try:
        conn = duckdb.connect(str(DB_PATH))
        
        # Get all table names
        tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
        
        if tables:
            print(f"🗑️  Dropping {len(tables)} table(s)...")
            # Drop all tables
            for table in tables:
                table_name = table[0]
                conn.execute(f'DROP TABLE "{table_name}"')
                print(f"  ✅ Dropped {table_name}")
        else:
            print("✅ Database was already empty")
        
        conn.close()
        
        # Reset the global file_id
        current_file_id = None
        
        return {
            "status": "reset",
            "tables_dropped": len(tables),
            "message": "Database cleared and file_id reset"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/upload")
def save_data(data: dict = Body(...)):
    global current_file_id
    
    file_id = str(uuid.uuid4())
    
    # Normalize and store in DuckDB
    try:
        ingest_and_normalize(data, file_id)
        current_file_id = file_id  # Set as the active file
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

@app.post("/ask")
def ask_question(question: str):
    """
    Ask a natural language question about a UAV log file.
    Uses the currently active file (most recent upload).
    """
    global current_file_id
    
    # Check if a file has been uploaded
    if not current_file_id:
        return {
            "answer": "No flight log file has been uploaded yet. Please upload a file first."
        }
    
    try:
        # Delegate to agent
        answer = run_agent(question, current_file_id)
        return {
            "answer": answer
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "answer": f"Error: {str(e)}"
        }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)