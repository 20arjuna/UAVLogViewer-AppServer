from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import uuid
import uvicorn
import json

# Import from our modules
from config import openai_client, load_system_prompt, DB_PATH
from ingestion import ingest_and_normalize
from tools import list_available_tables, get_table_schema, query_sql
import duckdb

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
        print(f"\n" + "="*60)
        print(f"❓ User Question: {question}")
        print(f"📁 Using file_id: {current_file_id}")
        print("="*60)
        
        # Load system prompt from file
        system_prompt = load_system_prompt()
        
        # Define tools for OpenAI function calling
        tools = [
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
        
        # Initial messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        
        # Call GPT-5.1 with tools
        response = openai_client.chat.completions.create(
            model="gpt-5.1",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        
        # If the agent wants to use tools, execute them
        if tool_calls:
            print(f"\n🧠 Agent wants to call {len(tool_calls)} tool(s):")
            
            # Add agent's response to messages
            messages.append(response_message)
            
            # Execute each tool call
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Log what the agent is doing
                print(f"\n🤖 Agent is calling: {function_name}")
                print(f"📥 Arguments: {json.dumps(function_args, indent=2)}")
                
                # Execute the appropriate tool
                if function_name == "list_available_tables":
                    # Use current_file_id instead of what agent provides
                    result = list_available_tables(current_file_id)
                elif function_name == "get_table_schema":
                    result = get_table_schema(function_args["table_name"])
                elif function_name == "query_sql":
                    # Special logging for SQL queries
                    print(f"🔍 SQL Query: {function_args['sql']}")
                    result = query_sql(function_args["sql"])
                else:
                    result = {"error": f"Unknown function: {function_name}"}
                
                # Log the result (truncate if too long)
                result_str = json.dumps(result, indent=2)
                if len(result_str) > 500:
                    print(f"📤 Result (truncated): {result_str[:500]}...")
                else:
                    print(f"📤 Result: {result_str}")
                
                # Add tool result to messages
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(result)
                })
            
            # Call the agent again with tool results
            print(f"\n🔄 Calling agent again with tool results...")
            second_response = openai_client.chat.completions.create(
                model="gpt-5.1",
                messages=messages
            )
            
            answer = second_response.choices[0].message.content
        else:
            # No tools needed, use direct response
            print(f"\n💬 Agent responding directly (no tools needed)")
            answer = response_message.content
        
        print(f"\n✅ Final Answer: {answer}")
        print("="*60 + "\n")
        
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