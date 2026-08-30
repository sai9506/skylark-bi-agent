import os
import json
import requests
import pandas as pd

from dotenv import load_dotenv

from deal_mapping import DEAL_COLUMN_MAPPING

from data_cleaner import (
    clean_dataframe,
    normalize_dates,
    normalize_sector
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

API_TOKEN = os.getenv("MONDAY_API_TOKEN")

URL = "https://api.monday.com/v2"


# ============================================================
# API TOKEN CHECK
# ============================================================

if not API_TOKEN:
    raise ValueError(
        "MONDAY_API_TOKEN not found in .env file"
    )


# ============================================================
# DEALS BOARD ID
# ============================================================

DEALS_BOARD_ID = os.getenv(
    "MONDAY_DEALS_BOARD_ID"
)

if not DEALS_BOARD_ID:
    raise ValueError(
        "MONDAY_DEALS_BOARD_ID not found in .env file"
    )

try:
    DEALS_BOARD_ID = int(DEALS_BOARD_ID)

except ValueError:
    raise ValueError(
        "MONDAY_DEALS_BOARD_ID must be a number"
    )


# ============================================================
# HEADERS
# ============================================================

HEADERS = {
    "Authorization": API_TOKEN,
    "Content-Type": "application/json"
}


# ============================================================
# FETCH ALL DEALS
# ============================================================

def fetch_all_deals(board_id=None):
    """
    Fetch all items from the Monday.com Deals board.

    Uses cursor-based pagination.

    Returns:
        list: Raw Monday.com deal items.
    """

    if board_id is None:
        board_id = DEALS_BOARD_ID

    all_items = []
    cursor = None

    print("\nFetching Deals from Monday.com...")
    print(f"Deals Board ID: {board_id}")

    while True:

        # ====================================================
        # FIRST PAGE
        # ====================================================

        if cursor is None:

            query = f"""
            query {{
                boards(ids: [{board_id}]) {{
                    id
                    name

                    items_page(limit: 100) {{
                        cursor

                        items {{
                            id
                            name

                            column_values {{
                                id
                                text
                                value
                                type
                            }}
                        }}
                    }}
                }}
            }}
            """

        # ====================================================
        # NEXT PAGE
        # ====================================================

        else:

            query = f"""
            query {{
                next_items_page(
                    limit: 100,
                    cursor: "{cursor}"
                ) {{
                    cursor

                    items {{
                        id
                        name

                        column_values {{
                            id
                            text
                            value
                            type
                        }}
                    }}
                }}
            }}
            """

        # ====================================================
        # API REQUEST
        # ====================================================

        try:

            response = requests.post(
                URL,
                json={
                    "query": query
                },
                headers=HEADERS,
                timeout=30
            )

            response.raise_for_status()

            result = response.json()

        except requests.RequestException as e:

            print("\nMonday.com connection error:")
            print(e)

            return []

        # ====================================================
        # API ERROR
        # ====================================================

        if "errors" in result:

            print("\nMonday.com API Error:")

            for error in result["errors"]:
                print(error)

            return []

        # ====================================================
        # GET PAGE
        # ====================================================

        try:

            if cursor is None:

                boards = result["data"]["boards"]

                if not boards:

                    print(
                        f"\nNo board found with ID: {board_id}"
                    )

                    return []

                board = boards[0]

                print(
                    f"Deals Board: {board.get('name')}"
                )

                page = board["items_page"]

            else:

                page = result["data"]["next_items_page"]

        except (
            KeyError,
            TypeError,
            IndexError
        ):

            print(
                "\nUnexpected Monday.com API response:"
            )

            print(
                json.dumps(
                    result,
                    indent=2
                )
            )

            return []

        # ====================================================
        # ADD ITEMS
        # ====================================================

        items = page.get(
            "items",
            []
        )

        all_items.extend(items)

        print(
            f"Fetched {len(all_items)} deals..."
        )

        # ====================================================
        # NEXT CURSOR
        # ====================================================

        cursor = page.get("cursor")

        # ====================================================
        # END
        # ====================================================

        if not cursor:
            break

    print(
        f"\nTotal raw deals fetched: {len(all_items)}"
    )

    return all_items


# ============================================================
# EXTRACT COLUMN VALUE
# ============================================================

def get_column_value(column):
    """
    Extract the best available value from a Monday.com column.

    Priority:

        1. text
        2. parsed JSON value
        3. raw value
    """

    text = column.get("text")
    value = column.get("value")

    # ========================================================
    # TEXT VALUE
    # ========================================================

    if text is not None and str(text).strip() != "":
        return text

    # ========================================================
    # NO VALUE
    # ========================================================

    if value is None or value == "":
        return ""

    # ========================================================
    # TRY JSON
    # ========================================================

    try:

        parsed = json.loads(value)

    except (
        json.JSONDecodeError,
        TypeError
    ):

        return value

    # ========================================================
    # JSON DICTIONARY
    # ========================================================

    if isinstance(parsed, dict):

        if "number" in parsed:
            return parsed["number"]

        if "amount" in parsed:
            return parsed["amount"]

        if "date" in parsed:
            return parsed["date"]

        if "value" in parsed:
            return parsed["value"]

        if "label" in parsed:
            return parsed["label"]

        if "percent" in parsed:
            return parsed["percent"]

    # ========================================================
    # JSON LIST
    # ========================================================

    if isinstance(parsed, list):

        return ", ".join(
            str(x)
            for x in parsed
        )

    # ========================================================
    # FALLBACK
    # ========================================================

    return parsed


# ============================================================
# CONVERT VALUE TO NUMBER
# ============================================================

def to_number(value):
    """
    Convert Monday.com numeric/currency values to float.
    """

    if value is None:
        return 0.0

    # ========================================================
    # NUMERIC
    # ========================================================

    if isinstance(
        value,
        (int, float)
    ):

        try:

            if pd.isna(value):
                return 0.0

        except Exception:
            pass

        return float(value)

    # ========================================================
    # STRING
    # ========================================================

    value = str(value).strip()

    if value == "":
        return 0.0

    # ========================================================
    # REMOVE FORMATTING
    # ========================================================

    value = (
        value
        .replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("%", "")
        .strip()
    )

    # ========================================================
    # CONVERT
    # ========================================================

    try:

        return float(value)

    except ValueError:

        return 0.0


# ============================================================
# GET DEALS
# ============================================================

def get_deals():
    """
    Fetch, clean and prepare Deals data.

    Returns:
        pandas.DataFrame
    """

    print(
        "\nLoading Deals from Monday.com..."
    )

    print(
        f"Deals Board ID: {DEALS_BOARD_ID}"
    )

    # ========================================================
    # FETCH RAW DATA
    # ========================================================

    items = fetch_all_deals(
        DEALS_BOARD_ID
    )

    if not items:

        print(
            "\nNo deals found."
        )

        return pd.DataFrame()

    # ========================================================
    # CREATE ROWS
    # ========================================================

    rows = []

    for item in items:

        row = {
            "Deal Name": item.get(
                "name",
                ""
            )
        }

        # ====================================================
        # COLUMN VALUES
        # ====================================================

        for column in item.get(
            "column_values",
            []
        ):

            column_id = column.get(
                "id"
            )

            if not column_id:
                continue

            # ------------------------------------------------
            # MAP COLUMN ID
            # ------------------------------------------------

            column_name = (
                DEAL_COLUMN_MAPPING.get(
                    column_id,
                    column_id
                )
            )

            # ------------------------------------------------
            # EXTRACT VALUE
            # ------------------------------------------------

            row[column_name] = (
                get_column_value(
                    column
                )
            )

        rows.append(row)

    # ========================================================
    # DATAFRAME
    # ========================================================

    df = pd.DataFrame(rows)

    # ========================================================
    # CLEAN DATAFRAME
    # ========================================================

    df = clean_dataframe(df)

    # ========================================================
    # DEAL VALUE
    # ========================================================

    if "Deal Value" in df.columns:

        df["Deal Value"] = (
            df["Deal Value"]
            .apply(to_number)
        )

    else:

        df["Deal Value"] = 0.0

    # ========================================================
    # CLOSE PROBABILITY
    # ========================================================

    if "Close Probability" in df.columns:

        df["Close Probability"] = (
            df["Close Probability"]
            .apply(to_number)
        )

    else:

        df["Close Probability"] = 0.0

    # ========================================================
    # FORECAST VALUE
    # ========================================================
    #
    # IMPORTANT:
    #
    # Monday.com's formula column
    # "deal_forecast_value"
    # is returning EMPTY.
    #
    # Therefore we calculate Forecast Value ourselves.
    #
    # Formula:
    #
    # Forecast Value =
    # Deal Value × Close Probability / 100
    #
    # ========================================================

    df["Calculated Forecast Value"] = (
        df["Deal Value"]
        * df["Close Probability"]
        / 100.0
    )

    # ========================================================
    # FORECAST VALUE
    # ========================================================
    #
    # Keep a standard "Forecast Value" column
    # for BI engine compatibility.
    #
    # ========================================================

    df["Forecast Value"] = (
        df["Calculated Forecast Value"]
    )

    # ========================================================
    # SECTOR
    # ========================================================

    if "Sector" in df.columns:

        df["Sector"] = (
            df["Sector"]
            .apply(normalize_sector)
        )

    else:

        df["Sector"] = "Unknown"

    # ========================================================
    # DATES
    # ========================================================

    date_columns = [
        "Created Date",
        "Expected Close Date",
        "Tentative Close Date",
        "Close Date"
    ]

    df = normalize_dates(
        df,
        date_columns
    )

    # ========================================================
    # DEBUG
    # ========================================================

    print(
        "\n===== NON-ZERO DEALS ====="
    )

    debug_columns = [
        "Deal Name",
        "Deal Value",
        "Close Probability",
        "Forecast Value",
        "Calculated Forecast Value",
        "Sector"
    ]

    existing_columns = [
        column
        for column in debug_columns
        if column in df.columns
    ]

    non_zero_deals = df[
        df["Deal Value"] > 0
    ]

    if not non_zero_deals.empty:

        print(
            non_zero_deals[
                existing_columns
            ].to_string(
                index=False
            )
        )

    else:

        print(
            "No non-zero deal values found."
        )

    # ========================================================
    # DEAL VALUE TOTAL
    # ========================================================

    total_deal_value = (
        df["Deal Value"]
        .sum()
    )

    print(
        "\n===== DEAL VALUE TOTAL ====="
    )

    print(
        "Total Deal Value:",
        total_deal_value
    )

    print(
        "Non-zero Deal Values:",
        int(
            (
                df["Deal Value"] > 0
            ).sum()
        )
    )

    # ========================================================
    # FORECAST VALUE TOTAL
    # ========================================================

    total_forecast_value = (
        df["Calculated Forecast Value"]
        .sum()
    )

    print(
        "\n===== FORECAST VALUE TOTAL ====="
    )

    print(
        "Total Forecast Value:",
        total_forecast_value
    )

    print(
        "Non-zero Forecast Values:",
        int(
            (
                df["Calculated Forecast Value"] > 0
            ).sum()
        )
    )

    # ========================================================
    # FINAL RETURN
    # ========================================================

    return df


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    df = get_deals()

    print(
        "\n===== DEALS DATA ====="
    )

    print(
        "Number of records:",
        len(df)
    )

    print(
        "Number of columns:",
        len(df.columns)
    )

    print(
        "\nColumn names:"
    )

    print(
        df.columns.tolist()
    )

    print(
        "\nFirst 5 records:"
    )

    print(
        df.head()
    )

    # ========================================================
    # FINAL DEAL VALUE CHECK
    # ========================================================

    if not df.empty:

        print(
            "\n===== FINAL DEAL VALUE CHECK ====="
        )

        check_columns = [
            "Deal Name",
            "Deal Value",
            "Close Probability",
            "Forecast Value",
            "Calculated Forecast Value",
            "Sector"
        ]

        existing_columns = [
            column
            for column in check_columns
            if column in df.columns
        ]

        print(
            df[
                existing_columns
            ]
            .head(20)
            .to_string(
                index=False
            )
        )