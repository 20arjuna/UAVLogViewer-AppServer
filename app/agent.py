"""
Agent logic for processing questions with tool calling
"""
import json
from config import openai_client, load_system_prompt
from tools import list_available_tables, get_table_schema, query_sql, control_playback, seek_to_timestamp, seek_to_mode
from tool_registry import TOOL_DEFINITIONS


def build_system_prompt(file_id: str) -> str:
    """Build the system prompt with injected file_id"""
    system_prompt = load_system_prompt()
    
    # Inject current session state based on whether a file is uploaded
    if file_id:
        system_prompt += f"""

==========================================
CURRENT SESSION STATE
==========================================
Flight log file ID: {file_id}

This file has been uploaded and normalized into the database.
The data is READY to query - do NOT ask the user to upload a file.

When you call list_available_tables(), use file_id="{file_id}".
Tables will be prefixed with: log_{file_id.replace('-', '_')}_

The number of tables varies - could be many (ATT, GPS, BATT, etc.) or just one combined table.
Work with WHATEVER tables you find - don't complain about missing tables.

Start by calling list_available_tables() to see what data is available, then proceed with your analysis.
"""
    else:
        system_prompt += """

==========================================
CURRENT SESSION STATE
==========================================
NO FLIGHT LOG FILE UPLOADED YET

The user has not uploaded any flight log data yet.

YOU CAN STILL BE HELPFUL:
- Answer general questions about ArduPilot, flight modes, telemetry, best practices
- Explain concepts like GPS, IMU, EKF, flight modes (LOITER, RTL, AUTO, etc.)
- Discuss common issues, troubleshooting approaches, log analysis techniques
- Be friendly and educational!

YOU CANNOT:
- Use any tools (list_available_tables, get_table_schema, query_sql) - there's no data to query
- Analyze specific flight data or provide actual numbers from logs
- Make assumptions about their specific flight

If they ask you to analyze flight data, politely tell them:
"I'd love to analyze your flight data! To do that, please upload a flight log file (.bin or .tlog) using the file selector in the sidebar. Once uploaded, I can dive into the specifics!"

Be warm, helpful, and show your expertise even without data to analyze.
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
    elif function_name == "control_playback":
        result = control_playback(function_args["action"])
    elif function_name == "seek_to_timestamp":
        result = seek_to_timestamp(function_args["timestamp_ms"])
    elif function_name == "seek_to_mode":
        result = seek_to_mode(file_id, function_args["mode_name"])
    else:
        result = {"error": f"Unknown function: {function_name}"}
    
    # Log the result (truncate if too long)
    result_str = json.dumps(result, indent=2)
    if len(result_str) > 500:
        print(f"📤 Result (truncated): {result_str[:500]}...")
    else:
        print(f"📤 Result: {result_str}")
    
    return result


def run_agent(question: str, file_id: str, history: list = None, max_iterations: int = 10):
    """
    Generator that streams agent responses.
    
    Args:
        question: Current user question
        file_id: Current file being analyzed
        history: Previous conversation messages [{"role": "user", "content": "..."}, ...]
        max_iterations: Max tool calling iterations
    
    Yields events:
    - {"type": "token", "content": "..."} - streaming final answer tokens
    - {"type": "command", "action": "...", "params": {...}} - UI control command
    - {"type": "done"} - stream complete
    """
    print(f"\n" + "="*60)
    print(f"❓ User Question: {question}")
    print(f"📁 Using file_id: {file_id}")
    if history:
        print(f"📚 Conversation history: {len(history)} messages")
    print("="*60)
    
    # Build system prompt with file_id context
    system_prompt = build_system_prompt(file_id)
    
    # Build messages with conversation history
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history (if provided)
    if history:
        messages.extend(history)
    
    # Add current question
    messages.append({"role": "user", "content": question})
    
    # Agent loop - keep going until agent gives final answer or hits max iterations
    for iteration in range(max_iterations):
        print(f"\n🔄 Iteration {iteration + 1}/{max_iterations}")
        
        # Call GPT-5.1 with tools (no streaming during tool phase)
        response = openai_client.chat.completions.create(
            model="gpt-5.1",
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            stream=False
        )
        
        response_message = response.choices[0].message
        
        # Check if agent wants to use tools
        if not response_message.tool_calls:
            # No tool calls = agent ready to give final answer
            # NOW stream the final answer
            print(f"\n✅ Agent providing final answer with streaming...")
            
            # Re-call with streaming enabled for the final answer
            stream_response = openai_client.chat.completions.create(
                model="gpt-5.1",
                messages=messages,
                stream=True
            )
            
            for chunk in stream_response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)
                    yield {"type": "token", "content": content}
            
            print("\n" + "="*60 + "\n")
            yield {"type": "done"}
            return
        
        # Agent wants to use tools - execute them
        tool_names = [tc.function.name for tc in response_message.tool_calls]
        print(f"\n🧠 Agent wants to call {len(response_message.tool_calls)} tool(s): {tool_names}")
        
        # Add agent's response to messages
        messages.append(response_message)
        
        # Execute each tool call
        for tool_call in response_message.tool_calls:
            result = execute_tool(tool_call, file_id)
            
            # If tool result is a command, yield it to frontend immediately
            if isinstance(result, dict) and result.get("type") == "command":
                print(f"🎮 Yielding command to frontend: {result['action']}")
                yield result
            
            # Add tool result to messages
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": tool_call.function.name,
                "content": json.dumps(result)
            })
        
        # Loop continues - agent will see tool results and decide next step
    
    # Hit max iterations without final answer
    print(f"\n⚠️  Reached maximum iterations ({max_iterations})")
    print("="*60 + "\n")
    error_msg = f"I've reached the maximum number of analysis steps ({max_iterations}). Please try asking a more specific question or breaking it down into smaller parts."
    yield {"type": "token", "content": error_msg}
    yield {"type": "done"}

