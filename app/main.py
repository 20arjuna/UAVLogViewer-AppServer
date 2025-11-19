from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uuid
import uvicorn
import duckdb
import json
import os

# Import from our modules
from .config import DB_PATH
from .ingestion import ingest_and_normalize
from .agent import run_agent
from .conversation import save_message, get_conversation, clear_all_conversations

# Global state - tracks the currently active file_id
current_file_id = None


app = FastAPI(
    title="UAV Log Viewer API",
    description="Backend API for UAV Log Viewer",
    version="1.0.0"
)

# Configure CORS - allows frontend to communicate with backend
# In production, set CORS_ORIGINS env var to your frontend URL
cors_origins = os.getenv("CORS_ORIGINS", "*")
if cors_origins == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
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
        # Clear conversation history
        clear_all_conversations()
        print("🗑️  Cleared all conversation history")
        
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
            "message": "Database, conversation history, and file_id cleared"
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
def ask_question(question: str, session_id: str):
    """
    Ask a natural language question about a UAV log file (streaming).
    Uses conversation history for context.
    
    Args:
        question: The user's question
        session_id: Unique session identifier for conversation history
    """
    global current_file_id
    
    def generate():
        """Generator for Server-Sent Events"""
        try:
            # Get conversation history
            history = get_conversation(session_id)
            print(f"📚 Loaded {len(history)} messages from conversation history")
            
            # Save user's question
            save_message(session_id, "user", question)
            
            # Stream agent response (file_id can be None - agent will handle it)
            assistant_content = ""
            for event in run_agent(question, current_file_id, history):
                # Accumulate assistant response content
                if event.get("type") == "token":
                    assistant_content += event["content"]
                
                # Send each event as Server-Sent Event
                yield f"data: {json.dumps(event)}\n\n"
            
            # Save complete assistant response to history
            if assistant_content:
                save_message(session_id, "assistant", assistant_content)
                print(f"💾 Saved assistant response to conversation history")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # Friendly error message based on error type
            error_type = type(e).__name__
            
            if "RateLimitError" in error_type:
                friendly_msg = "Oops! I'm thinking a bit too fast right now. 🤔 Give me a few seconds and try again?"
            elif "APIError" in error_type or "APIConnectionError" in error_type:
                friendly_msg = "Hmm, having trouble connecting to my brain right now. 🧠 Could you try that again?"
            elif "AuthenticationError" in error_type:
                friendly_msg = "Looks like there's an authentication issue on my end. Check the OpenAI API key configuration!"
            else:
                friendly_msg = "Whoops! Hit a slight hiccup there. 😅 Mind trying that again?"
            
            # Send as token so it renders nicely in chat
            yield f"data: {json.dumps({'type': 'token', 'content': friendly_msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)