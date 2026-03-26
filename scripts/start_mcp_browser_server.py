#!/usr/bin/env python3
"""
Startup script for MCP Browser HTTP Server
Loads environment variables and starts the server with proper configuration.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file in project root
env_file = Path(__file__).resolve().parent.parent / '.env'
if env_file.exists():
    print(f"Loading environment from: {env_file}")
    load_dotenv(env_file)
else:
    print("No .env file found. Using system environment variables.")
    print("Tip: Copy mcp_config.env.example to .env and configure your settings.")

# Verify critical environment variables are set
required_vars = {
    'MCP_LLM_PROVIDER': 'LLM provider (google, openai, anthropic, openrouter, etc.)',
}

# Check if at least one API key is set based on provider
provider = os.environ.get('MCP_LLM_PROVIDER', 'google').lower()
api_key_map = {
    'google': ['GOOGLE_API_KEY', 'MCP_LLM_GOOGLE_API_KEY'],
    'openai': ['OPENAI_API_KEY', 'MCP_LLM_OPENAI_API_KEY'],
    'anthropic': ['ANTHROPIC_API_KEY', 'MCP_LLM_ANTHROPIC_API_KEY'],
    'openrouter': ['OPENROUTER_API_KEY', 'MCP_LLM_OPENROUTER_API_KEY', 'MCP_LLM_API_KEY'],
    'groq': ['GROQ_API_KEY', 'MCP_LLM_GROQ_API_KEY', 'MCP_LLM_API_KEY'],
    'deepseek': ['DEEPSEEK_API_KEY', 'MCP_LLM_DEEPSEEK_API_KEY', 'MCP_LLM_API_KEY'],
    'cerebras': ['CEREBRAS_API_KEY', 'MCP_LLM_CEREBRAS_API_KEY', 'MCP_LLM_API_KEY'],
    'browser_use': ['BROWSER_USE_API_KEY', 'MCP_LLM_BROWSER_USE_API_KEY', 'MCP_LLM_API_KEY'],
    'vercel': ['VERCEL_API_KEY', 'MCP_LLM_VERCEL_API_KEY', 'MCP_LLM_API_KEY'],
    'azure_openai': ['AZURE_OPENAI_API_KEY', 'MCP_LLM_AZURE_OPENAI_API_KEY', 'MCP_LLM_API_KEY'],
}

missing_vars = []
for var, description in required_vars.items():
    if not os.environ.get(var):
        missing_vars.append(f"  - {var}: {description}")

# Check API key for selected provider
if provider in api_key_map:
    api_keys = api_key_map[provider]
    has_key = any(os.environ.get(key) for key in api_keys)
    if not has_key:
        missing_vars.append(f"  - {' or '.join(api_keys)}: API key for {provider} provider")

if missing_vars:
    print("\n❌ ERROR: Missing required environment variables:")
    print("\n".join(missing_vars))
    print("\nPlease set these in your .env file or system environment.")
    print("See config/mcp_config.env.example for reference.")
    sys.exit(1)

# Create research output directory if it doesn't exist
research_dir = os.environ.get('MCP_RESEARCH_SAVE_DIRECTORY')
if research_dir:
    Path(research_dir).mkdir(parents=True, exist_ok=True)
    print(f"Research output directory: {research_dir}")

# Display configuration (LLM is used by the background MCP server at MCP_BROWSER_USE_HTTP_URL; start it with start_mcp_browser_use_http_server.py to use this same config)
print("\n" + "="*50)
print("MCP Browser HTTP Server Configuration")
print("="*50)
print(f"LLM Provider: {os.environ.get('MCP_LLM_PROVIDER', 'ollama')} (used by MCP server at MCP_BROWSER_USE_HTTP_URL)")
print(f"Model: {os.environ.get('MCP_LLM_MODEL_NAME', 'default')}")
print(f"Base URL: {os.environ.get('MCP_LLM_BASE_URL', '(provider default)')}")
print(f"Browser Headless: {os.environ.get('MCP_BROWSER_HEADLESS', 'false')}")
print(f"Browser CDP URL: {os.environ.get('MCP_BROWSER_CDP_URL', '(not set)')}")
print(f"Browser Executable: {os.environ.get('MCP_BROWSER_EXECUTABLE_PATH', '(auto)')}")
print(f"Browser User Data Dir: {os.environ.get('MCP_BROWSER_USER_DATA_DIR', '(not set)')}")
print(f"Browser Profile Dir: {os.environ.get('MCP_BROWSER_PROFILE_DIRECTORY', 'Default')}")
print(f"Agent Max Steps: {os.environ.get('MCP_AGENT_MAX_STEPS', '20')}")
print(f"Agent Use Vision: {os.environ.get('MCP_AGENT_USE_VISION', 'true')}")
print(f"Research Save Directory: {os.environ.get('MCP_RESEARCH_SAVE_DIRECTORY', '(not set)')}")
print(f"Research Max Searches: {os.environ.get('MCP_RESEARCH_MAX_SEARCHES', '5')}")
print(f"Server Port: {os.environ.get('PORT', '5001')}")
print(f"Server Host: {os.environ.get('HOST', '0.0.0.0')}")
print("Note: Browser tasks run on the MCP server. Start it with start_mcp_browser_use_http_server.py so it uses this same LLM.")
print("="*50 + "\n")

# Import and start the server (ensure project root is on path)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from src.servers.mcp_browser_server import main
    print("Starting MCP Browser HTTP Server...")
    print("Press Ctrl+C to stop\n")
    main()
except KeyboardInterrupt:
    print("\n\nServer stopped by user.")
    sys.exit(0)
except Exception as e:
    print(f"\n❌ ERROR: Failed to start server: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

