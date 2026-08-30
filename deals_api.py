import os
import requests
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

MONDAY_API_URL = "https://api.monday.com/v2"

MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")

if not MONDAY_API_TOKEN:
    raise ValueError(
        "MONDAY_API_TOKEN is missing. "
        "Add it to your .env file locally or "
        "Streamlit Cloud → Manage app → Settings → Secrets."
    )


# ============================================================
# HEADERS
# ============================================================

HEADERS = {
    "Authorization": MONDAY_API_TOKEN,
    "Content-Type": "application/json",
    "API-Version": "2026-07"
}


# ============================================================
# GENERIC MONDAY API REQUEST
# ============================================================

def monday_request(query, variables=None):

    payload = {
        "query": query
    }

    if variables:
        payload["variables"] = variables

    try:

        response = requests.post(
            MONDAY_API_URL,
            headers=HEADERS,
            json=payload,
            timeout=30
        )

        response.raise_for_status()

        result = response.json()

        # GraphQL errors
        if "errors" in result:
            error_messages = []

            for error in result["errors"]:
                error_messages.append(
                    error.get("message", "Unknown GraphQL error")
                )

            raise RuntimeError(
                "Monday API error: "
                + " | ".join(error_messages)
            )

        return result.get("data", {})

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Monday API request timed out."
        )

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Could not connect to Monday.com API."
        )

    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"Monday API HTTP error: {e}"
        )

    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Monday API request failed: {e}"
        )


# ============================================================
# GET DEALS
# ============================================================

def get_deals(board_id):

    query = """
    query ($board_id: ID!) {

        boards(ids: [$board_id]) {

            id
            name

            items_page(limit: 500) {

                items {

                    id
                    name

                    column_values {

                        id
                        text
                        value

                    }
                }
            }
        }
    }
    """

    variables = {
        "board_id": str(board_id)
    }

    data = monday_request(
        query,
        variables
    )

    boards = data.get("boards", [])

    if not boards:
        raise RuntimeError(
            f"No Monday board found with ID {board_id}."
        )

    board = boards[0]

    return board.get(
        "items_page",
        {}
    ).get(
        "items",
        []
    )


# ============================================================
# GET BOARDS
# ============================================================

def get_boards():

    query = """
    query {

        boards(limit: 100) {

            id
            name

        }
    }
    """

    data = monday_request(query)

    return data.get(
        "boards",
        []
    )


# ============================================================
# TEST API CONNECTION
# ============================================================

def test_connection():

    query = """
    query {

        me {

            id
            name
            email

        }
    }
    """

    data = monday_request(query)

    return data.get("me")


# ============================================================
# MAIN TEST
# ============================================================

if __name__ == "__main__":

    try:

        user = test_connection()

        print("Monday.com connection successful!")

        print(
            f"User: {user.get('name')}"
        )

        print(
            f"Email: {user.get('email')}"
        )

    except Exception as e:

        print(
            f"Connection failed: {e}"
        )