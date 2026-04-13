"""ReadLoop 配置"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# --- Claude (primary) ---
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
CLAUDE_BASE_URL = os.environ.get("CLAUDE_BASE_URL", "https://api.ccodezh.com/v1")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6-n")

# --- DeepSeek (fallback) ---
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# --- Paths ---
REFERENCE_DIRS = [
    Path(os.environ.get("REFERENCE_DIR_1", "D:/wu/reference paper")),
    Path(os.environ.get("REFERENCE_DIR_2", "D:/agentmemory/papers")),
]
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "D:/wu/output"))

# --- Derived output paths ---
GRAPH_DIR = OUTPUT_DIR / "knowledge_graph"
MEMORY_DIR = OUTPUT_DIR / "memory"
REVIEWS_DIR = OUTPUT_DIR / "reviews"
EVOLUTION_DIR = OUTPUT_DIR / "evolution"
PROPOSALS_DIR = OUTPUT_DIR / "proposals"

# --- Model params ---
MAX_TOKENS = 16000  # Claude Sonnet supports large output
TEMPERATURE = 0.4
