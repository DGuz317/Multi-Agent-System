import os
import logging
import uvicorn
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from .instructions import exchange_agent_instruction
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams

load_dotenv()

exchange_agent_tool_set=MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp")
    ),
    tool_filter=["get_current_date","get_exchange_rate"]
)

root_agent = Agent(
    name="exchange_agent",
    model="gemini-2.5-flash",
    description=(
        "An agent that gives information about the exchange rates"
    ),
    instruction=exchange_agent_instruction,
    tools=[exchange_agent_tool_set]
)

app = get_fast_api_app(
    agents_dir=os.path.abspath(os.path.dirname(r"C:/Users/nvdung1/Desktop/test/root_agent/")),
    web=False,
    a2a=True
)

# app=to_a2a(root_agent, port=10002)

# print("\n" + "="*50)
# print("URL list (ENDPOINTS) created:")
# print("="*50)

# for route in app.routes:
#     if hasattr(route, "methods") and hasattr(route, "path"):
#         methods = ", ".join(route.methods)
#         print(f"[{methods:^10}] -> {route.path}")
#     elif hasattr(route, "path"):
#         print(f"[  MOUNTED  ] -> {route.path}")

# print("="*50 + "\n")

# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=10002)