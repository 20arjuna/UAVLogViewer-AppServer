"""
Agent logic for processing questions with tool calling
"""
import json
from config import openai_client, load_system_prompt
from tools import list_available_tables, get_table_schema, query_sql
from tool_registry import TOOL_DEFINITIONS


def build_system_prompt(file_id: str) -> str:
    """Build the system prompt with injected file_id"""
    system_prompt = load_system_prompt()
    
    # Inject current file_id into the prompt so agent knows what to query
    system_prompt += f"""

==========================================
CURRENT SESSION STATE
==========================================
Flight log file ID: {file_id}

This file has been uploaded and normalized into the database.
The data is READY to query - do NOT ask the user to upload a file.

When you call list_available_tables(), use file_id="{file_id}".
Tables will be named like: log_{file_id.replace('-', '_')}_ATT, log_{file_id.replace('-', '_')}_GPS_0_, etc.

Start by calling list_available_tables() to see what data is available, then proceed with your analysis.
"""
    return system_prompt


def execute_tool(tool_call, file_id: str) -> dict:
    """Execute a single tool call"""
    function_name = tool_call.function.name
    function_args = json.loads(tool_call.function.arguments)
    
    # Log what the agent is doing
    print(f"\n🤖 Agent is calling: {function_name}")
    print(f"📥 Arguments: {json.dumps(function_args, indent=2)}")
    
    # Execute the appropriate tool
    if function_name == "list_available_tables":
        # Use current_file_id instead of what agent provides
        result = list_available_tables(file_id)
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
    
    return result


def run_agent(question: str, file_id: str) -> str:
    """
    Run the agent to answer a question.
    NOTE: Current implementation only handles ONE round of tool calls.
    """
    print(f"\n" + "="*60)
    print(f"❓ User Question: {question}")
    print(f"📁 Using file_id: {file_id}")
    print("="*60)
    
    # Build system prompt with file_id context
    system_prompt = build_system_prompt(file_id)
    
    # Initial messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    # Call GPT-5.1 with tools
    response = openai_client.chat.completions.create(
        model="gpt-5.1",
        messages=messages,
        tools=TOOL_DEFINITIONS,
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
            result = execute_tool(tool_call, file_id)
            
            # Add tool result to messages
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": tool_call.function.name,
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
    
    return answer

