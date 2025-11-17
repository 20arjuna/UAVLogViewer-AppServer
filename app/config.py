"""
Configuration and shared constants for UAV Log Viewer API
"""
from pathlib import Path
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent  # UAVLogViewer-AppServer/
TMP_DIR = BASE_DIR / "tmp" / "uav_logs"
TMP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = BASE_DIR / "tmp" / "uav_logs.duckdb"
PROMPT_PATH = BASE_DIR / "prompt.txt"

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def load_system_prompt() -> str:
    """Load the system prompt from prompt.txt"""
    try:
        return PROMPT_PATH.read_text()
    except FileNotFoundError:
        return "You are a helpful assistant that answers questions about UAV flight logs."

