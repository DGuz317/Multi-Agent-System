import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from .instructions import country_agent_instruction
from .tools import get_country_info, get_public_holidays, get_weather_forecast, get_current_date, get_exchange_rate

load_dotenv()

GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY")

exchange_agent=Agent(
    name="exchange_agent",
    model="gemini-2.5-flash",
    description=(
        "An agent that gives information about the exchange rates"
    ),
    instruction=exchange_agent_instruction,
    tools=[get_current_date, get_exchange_rate]
)

country_agent = Agent(
    name="country_agent", #mandatory
    model="gemini-2.5-flash", #mandatory
    description="An agent that provides information about the country",
    instruction=country_agent_instruction,
    tools=[get_current_date, get_country_info, get_public_holidays, get_weather_forecast],
    sub_agents=[exchange_agent]
)
root_agent=country_agent
#We have to define it as a root agent.