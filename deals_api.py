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

URL = "https://api.monday.com/v2"


# ============================================================
# GET SECRET
# ============================================================

def get_secret(name, default=None):
    """
    Get secret from:
    1. Environment variable
    2. Streamlit secrets
    3. Default value
    """

    # --------------------------------------------------------
    # Local .env / environment
    # --------------------------------------------------------

    value = os.getenv(name)

    if value:
        return value.strip()


    # --------------------------------------------------------
    # Streamlit Cloud secrets
    # --------------------------------------------------------

    try:
        import streamlit as st

        if name in st.secrets:
            value = st.secrets[name]

            if value:
                return str(value).strip()

    except Exception:
        pass


    return default


# ============================================================
# MONDAY CONFIGURATION
# ============================================================

API_TOKEN = get_secret("MONDAY_API_TOKEN")

DEALS_BOARD_ID = get_secret(
    "MONDAY_DEALS_BOARD_ID",
    "5030965311"
)


# ============================================================
# VALIDATE BOARD ID
# ============================================================

try:

    DEALS_BOARD_ID = int(DEALS_BOARD_ID)

except (ValueError, TypeError):

    raise ValueError(
        "MONDAY_DEALS_BOARD_ID must be a number."
    )


# ============================================================
# HEADERS
# ============================================================

def get_headers():

    token = get_secret("MONDAY_API_TOKEN")

    if not token:

        raise ValueError(
            "MONDAY_API_TOKEN is missing. "
            "Add it to your .env file locally or "
            "Streamlit Cloud → Settings → Secrets."
        )

    return {
        "Authorization": token,
        "Content-Type": "application/json"
    }


# ============================================================
# FETCH ALL DEALS
# ============================================================

def fetch_all_deals(board_id=None):

    """
    Fetch all deals from Monday.com.

    Uses cursor-based pagination.
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
                json={"query": query},
                headers=get_headers(),
                timeout=30
            )

            response.raise_for_status()

            result = response.json()

        except requests.exceptions.Timeout:

            print("Monday.com request timed out.")

            return []

        except requests.exceptions.RequestException as e:

            print(
                f"Monday.com connection error: {e}"
            )

            return []

        except ValueError:

            print(
                "Monday.com returned invalid JSON."
            )

            return []


        # ====================================================
        # GRAPHQL ERROR
        # ====================================================

        if "errors" in result:

            print("\nMonday.com API Error:")

            for error in result["errors"]:

                print(
                    error.get(
                        "message",
                        error
                    )
                )

            return []


        # ====================================================
        # GET PAGE
        # ====================================================

        try:

            if cursor is None:

                boards = (
                    result
                    .get("data", {})
                    .get("boards", [])
                )

                if not boards:

                    print(
                        f"No board found with ID: "
                        f"{board_id}"
                    )

                    return []

                board = boards[0]

                print(
                    f"Deals Board: "
                    f"{board.get('name', 'Unknown')}"
                )

                page = board["items_page"]

            else:

                page = (
                    result
                    .get("data", {})
                    .get("next_items_page")
                )

                if not page:

                    print(
                        "No next page returned."
                    )

                    break

        except (
            KeyError,
            TypeError,
            IndexError
        ):

            print(
                "\nUnexpected Monday.com response:"
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
        # STOP
        # ====================================================

        if not cursor:

            break


    print(
        f"\nTotal raw deals fetched: "
        f"{len(all_items)}"
    )

    return all_items


# ============================================================
# EXTRACT COLUMN VALUE
# ============================================================

def get_column_value(column):

    """
    Extract the best available value
    from a Monday.com column.
    """

    text = column.get("text")
    value = column.get("value")
    column_type = column.get("type")


    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    if (
        text is not None
        and str(text).strip() != ""
    ):

        return text


    # --------------------------------------------------------
    # EMPTY
    # --------------------------------------------------------

    if (
        value is None
        or value == ""
    ):

        return ""


    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    try:

        parsed = json.loads(value)

    except (
        json.JSONDecodeError,
        TypeError
    ):

        return value


    # --------------------------------------------------------
    # DICTIONARY
    # --------------------------------------------------------

    if isinstance(parsed, dict):

        # Number
        if "number" in parsed:
            return parsed["number"]

        # Amount
        if "amount" in parsed:
            return parsed["amount"]

        # Date
        if "date" in parsed:
            return parsed["date"]

        # Value
        if "value" in parsed:
            return parsed["value"]

        # Label
        if "label" in parsed:
            return parsed["label"]

        # Percent
        if "percent" in parsed:
            return parsed["percent"]


    # --------------------------------------------------------
    # LIST
    # --------------------------------------------------------

    if isinstance(parsed, list):

        return ", ".join(
            str(x)
            for x in parsed
        )


    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    return parsed


# ============================================================
# CONVERT VALUE TO NUMBER
# ============================================================

def to_number(value):

    """
    Convert Monday.com number/currency values to float.
    """

    if value is None:

        return 0.0


    # --------------------------------------------------------
    # NUMBER
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # STRING
    # --------------------------------------------------------

    value = str(value).strip()


    if value == "":

        return 0.0


    # --------------------------------------------------------
    # CLEAN FORMATTING
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # CONVERT
    # --------------------------------------------------------

    try:

        return float(value)

    except (
        ValueError,
        TypeError
    ):

        return 0.0


# ============================================================
# GET DEALS
# ============================================================

def get_deals():

    """
    Fetch and clean Deals data.

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
    # FETCH
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


        for column in item.get(
            "column_values",
            []
        ):

            column_id = column.get(
                "id"
            )


            # ------------------------------------------------
            # MAP COLUMN
            # ------------------------------------------------

            column_name = (
                DEAL_COLUMN_MAPPING.get(
                    column_id,
                    column_id
                )
            )


            # ------------------------------------------------
            # VALUE
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
    # CLEAN DATA
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
    # CALCULATED FORECAST
    # ========================================================

    df["Calculated Forecast Value"] = (
        df["Deal Value"]
        * df["Close Probability"]
        / 100.0
    )


    # ========================================================
    # SECTOR
    # ========================================================

    if "Sector" in df.columns:

        df["Sector"] = (
            df["Sector"]
            .apply(normalize_sector)
        )


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
    # TOTAL DEAL VALUE
    # ========================================================

    total_deal_value = (
        df["Deal Value"].sum()
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
    # TOTAL FORECAST
    # ========================================================

    total_forecast_value = (
        df[
            "Calculated Forecast Value"
        ].sum()
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
                df[
                    "Calculated Forecast Value"
                ] > 0
            ).sum()
        )
    )


    return df


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    try:

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


        if not df.empty:

            print(
                "\n===== FINAL DEAL VALUE CHECK ====="
            )


            check_columns = [
                "Deal Name",
                "Deal Value",
                "Close Probability",
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

    except Exception as e:

        print(
            "\nERROR:"
        )

        print(e)