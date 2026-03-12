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
    agents_dir=os.path.abspath(os.path.dirname(r"C:/Users/nvdung1/Desktop/test/country_agent/exchange_agent")),
    web=True,
    a2a=True
)