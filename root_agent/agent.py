import logging
import os

from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH
from dotenv import load_dotenv
from google.adk.agents import Agent
from .instructions import country_agent_instruction, exchange_agent_instruction
# from .tools import get_country_info, get_public_holidays, get_weather_forecast, get_current_date, get_exchange_rate
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.cli.fast_api import get_fast_api_app

import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

load_dotenv()

country_agent_tool_set=MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp")
    ),
    tool_filter=["get_country_info","get_public_holidays","get_weather_forecast","get_current_date"]
)

# exchange_agent_tool_set=MCPToolset(
#     connection_params=StreamableHTTPConnectionParams(
#         url=os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp")
#     ),
#     tool_filter=["get_current_date","get_exchange_rate"]
# )

exchange_agent = RemoteA2aAgent(
    name="exchange_agent",
    description="An agent that gives information about the exchange rates",
    agent_card=(
        f"http://localhost:10002/a2a/sub_agent{AGENT_CARD_WELL_KNOWN_PATH}"
    ),
)

# exchange_agent = Agent(
#     name="exchange_agent",
#     model="gemini-2.5-flash",
#     description=(
#         "An agent that gives information about the exchange rates"
#     ),
#     instruction=exchange_agent_instruction,
#     tools=[exchange_agent_tool_set]
# )

country_agent = Agent(
    name="country_agent", #mandatory
    model="gemini-2.5-flash", #mandatory
    description="An agent that provides information about the country",
    instruction=country_agent_instruction,
    tools=[country_agent_tool_set],
    sub_agents=[exchange_agent]
)


root_agent = country_agent

# app = to_a2a(root_agent, port=10003)
app = get_fast_api_app(
    agents_dir=os.path.abspath(os.path.dirname(r"C:/Users/nvdung1/Desktop/test/")),
    web=True,
    a2a=True
)
