from fastmcp import FastMCP
import datetime
import openmeteo_requests
import pandas as pd
import json
from typing import Optional, Dict, Any, List
import requests
import os
import logging
import asyncio


logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

mcp = FastMCP("My MCP Server")

@mcp.tool
def get_country_info(country_name: str) -> str:
    """
    Fetches specific information (capital, languages, flag details, maps,
    population, and capital coordinates) for a given country name
    using the REST Countries API.

    Args:
        country_name (str): The common or official name of the country
        (e.g., "Turkey", "South Korea", "USA").

    Returns:
        str: A JSON string containing the extracted country data or an error
        message.
    """
    encoded_country_name = requests.utils.quote(country_name)
    url = f"https://restcountries.com/v3.1/name/{encoded_country_name}"
    try:
        # country_cert_path = r"C:\Users\nvdung1\Desktop\test\cert\restcountries.crt"
        response = requests.get(url, verify=False, timeout=10)
        response.raise_for_status()
        data: List[Dict[str, Any]] = response.json()
        if not data:
            return json.dumps({"error": f"Country information not found for'{country_name}'."})

        country_data: Dict[str, Any] = data[0]
        capital: List[str] = country_data.get("capital", ["N/A"])
        languages: Dict[str, str] = country_data.get("languages", {})
        flag_emoji: str = country_data.get("flag", "N/A")
        maps: Dict[str, str] = country_data.get("maps", {})
        flags_info: Dict[str, Any] = country_data.get("flags", {})
        capital_info: Dict[str, Any] = country_data.get("capitalInfo", {})
        capital_latlng: List[float] = capital_info.get("latlng", [None, None])
        population: int = country_data.get("population", 0)
        extracted_info: Dict[str, Any] = {
            "country_name": country_data.get("name", {}).get("common", country_name),
            "capital": capital[0] if capital else "N/A", # Use the first capital if available
            "population": population,
            "languages": list(languages.values()), # Convert language names to a list
            "flag_emoji": flag_emoji,
            "flags_images": {
                "png": flags_info.get("png"),
                "svg": flags_info.get("svg"),
                "alt_text": flags_info.get("alt")
            },
            "maps_urls": {
                "googleMaps": maps.get("googleMaps"),
                "openStreetMaps": maps.get("openStreetMaps")
            },
            "capital_coordinates": {
                "latitude": capital_latlng[0],
                "longitude": capital_latlng[1]
            }
        }

        return json.dumps(extracted_info, indent=4)

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        if status_code == 404:
            return json.dumps({"error": f"Country not found. Please check the spelling for '{country_name}'."})
        else:
            return json.dumps({"error": f"HTTP Error {status_code}: Could not retrieve data for '{country_name}'. Details: {e}"})

    except Exception as e:
        return json.dumps({"error": f"An unexpected error occurred: {e}"})

@mcp.tool
def get_weather_forecast(latitude: float, longitude: float, model: str) -> str:
    """
    Returns the daily maximum and minimum temperature forecasts for the
    specified location and weather model using the Open-Meteo API.

    NOTE: The 'latitude' and 'longitude' parameters are REQUIRED.

    Args:
        latitude (float): The latitude for the forecast
        longitude (float): The longitude for the forecast
        model (str): The weather model to use for the forecast. Defaults to None.

    Returns:
        str: A JSON string containing the weather forecast data.
    """
    try:
        openmeteo = openmeteo_requests.Client()
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ["temperature_2m_max", "temperature_2m_min"],
            "models": model,
            "forecast_days": 7
        }
        responses = openmeteo.weather_api(url, params=params)
        if not responses:
            return json.dumps({"error": "No response received from the weather API."})

        response = responses[0]
        daily = response.Daily()
        if daily is None or daily.Variables(0) is None:
            return json.dumps({"error": "Daily data is missing in the API response."})
        time_range = pd.date_range(
            start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
            end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
            freq = pd.Timedelta(seconds = daily.Interval()),
            inclusive = "left"
        )
        daily_temperature_2m_max = pd.Series(daily.Variables(0).ValuesAsNumpy(), index=time_range)
        daily_temperature_2m_min = pd.Series(daily.Variables(1).ValuesAsNumpy(), index=time_range)
        daily_dataframe = pd.DataFrame({
            "date": daily_temperature_2m_max.index.strftime('%Y-%m-%d'),
            "temperature_max_celsius": daily_temperature_2m_max.values,
            "temperature_min_celsius": daily_temperature_2m_min.values
        })
        json_output = daily_dataframe.to_json(orient='records', indent=4)
        return json_output

    except Exception as e:
        return json.dumps({"error": f"An error occurred during API call or data processing: {e}"})

@mcp.tool
def get_public_holidays(year: int, country_code: str) -> str:
    """
    Fetches the list of public holidays for a specified year and country
    and returns their local and English names.

    Args:
        year (int): The year for which to retrieve the holidays (e.g., 2025).
        country_code (str): The two-letter ISO 3166-1 alpha-2 country code (e.g., "TR" for Turkey, "US" for USA).

    Returns:
        str: A JSON string containing the date, local name, and English name or the holidays, or an error message.
    """
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}"
    try:
        # holiday_cert_path = r'C:\Users\nvdung1\Desktop\test\cert\nager.at.crt'
        response = requests.get(url, verify=False, timeout=10)
        response.raise_for_status()
        data: List[Dict[str, Any]] = response.json()
        if not data:
            return json.dumps({"result": f"No public holidays found for country code '{country_code}' in {year}."})
        extracted_holidays: List[Dict[str, str]] = []

        for holiday in data:
            extracted_holidays.append({
                "date": holiday.get("date"),
                "localName": holiday.get("localName"),
                "englishName": holiday.get("name")
            })

        return json.dumps(extracted_holidays, indent=4)

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code

        if status_code == 404:
            return json.dumps({"error": f"Invalid country code or unsupported year/country combination: '{country_code}' in {year}."})
        else:
            return json.dumps({"error": f"HTTP Error {status_code}: Could not retrieve holidays. Details: {e}"})

    except Exception as e:
        return json.dumps({"error": f"An unexpected error occurred: {e}"})

@mcp.tool
def get_current_date() -> str:
    """
    Retrieves the current date, time, and timezone information at the moment the function is executed.

    Args: 
        None

    Returns:
        str: A JSON string containing the current date and time information.
    """
    try:
        current_datetime_utc = datetime.datetime.now(datetime.timezone.utc)
        current_info: Dict[str, Any] = {"current_date": current_datetime_utc.strftime("%Y-%m-%d"),}

        return json.dumps(current_info, indent=4)

    except Exception as e:
        return json.dumps({"error": f"An unexpected error occurred while fetching the current date: {e}"})

@mcp.tool
def get_exchange_rate(
    currency_from: str = "USD",
    currency_to: str = "KRW",
    currency_date: str = "latest", ) -> dict:
    """
    Retrieves the exchange rate between two currencies for a specified date.
    Uses the Frankfurter API (https://api.frankfurter.app/) to fetch exchange rate data.

    Args:
    currency_from: Base currency (3-letter currency code). The default is "USD" (US Dollar).
    currency_to: Target currency (3-letter currency code). The default is "KRW" (Korean Won).
    currency_date: Date to query the exchange rate for. Default is "latest" for the most recent rate.
    For historical rates, specify in YYYY-MM-DD format.

    Returns:
    dict: A dictionary containing exchange rate information.
    Example: {"amount": 1.0, "base": "USD", "date": "2023-11-24", "rates": {"EUR": 0.95534}}
    """
    url = f"https://api.frankfurter.app/{currency_date}"

    try:
        response = requests.get(
            url, 
            params={"from": currency_from, "to": currency_to},
            verify=False, 
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}


if __name__ == "__main__":
    logger.info(f"🚀 MCP server started on port {os.getenv('PORT', 8001)}")
    # Could also use 'sse' transport, host="0.0.0.0" required for Cloud Run.
    asyncio.run(
        mcp.run_async(
            transport="http",
            host="0.0.0.0",
            port=os.getenv("PORT", 8001),
        )
    )