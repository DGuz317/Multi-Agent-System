import logging
import os
from dotenv import load_dotenv
from google.adk.agents import Agent
import uvicorn
from google.adk.cli.fast_api import get_fast_api_app
from .instructions import exchange_agent_instruction
# from .tools import get_country_info, get_public_holidays, get_weather_forecast, get_current_date, get_exchange_rate
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams
from google.adk.a2a.utils.agent_to_a2a import to_a2a

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
 
# AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

app = get_fast_api_app(
    agents_dir=os.path.abspath(os.path.dirname(r"C:/Users/nvdung1/Desktop/test/root_agent/")),
    web=False,
    a2a=True
)

# app=to_a2a(root_agent, port=10002)

# print("\n" + "="*50)
# print("DANH SÁCH CÁC URL (ENDPOINTS) ĐÃ ĐƯỢC TẠO:")
# print("="*50)

# for route in app.routes:
#     # Kiểm tra nếu là route API thông thường
#     if hasattr(route, "methods") and hasattr(route, "path"):
#         methods = ", ".join(route.methods)
#         print(f"[{methods:^10}] -> {route.path}")
#     # Kiểm tra nếu là các app được mount (như các router con của ADK)
#     elif hasattr(route, "path"):
#         print(f"[  MOUNTED  ] -> {route.path}")

# print("="*50 + "\n")

# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=10002)