import os
import requests
from dotenv import load_dotenv

load_dotenv()


def get_api_base_url():

    return os.getenv(
        "OFFICEMATE_API_BASE_URL",
        ""
    ).strip()


def get_live_data(endpoint):

    base_url = get_api_base_url()

    if not base_url:
        return None, "External API is not configured."

    url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")

    try:

        response = requests.get(
            url,
            timeout=10
        )

        response.raise_for_status()

        return response.json(), None

    except requests.RequestException as exc:

        return None, str(exc)