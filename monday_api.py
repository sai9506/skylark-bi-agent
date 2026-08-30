import os
import json
import requests
import pandas as pd

from dotenv import load_dotenv
from column_mapping import COLUMN_MAPPING

from data_cleaner import (
    clean_dataframe,
    normalize_dates,
    normalize_status,
    normalize_sector
)


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()

API_TOKEN = os.getenv("MONDAY_API_TOKEN")

URL = "https://api.monday.com/v2"

# Work Orders board
BOARD_ID = 5030965728

HEADERS = {
    "Authorization": API_TOKEN,
    "Content-Type": "application/json"
}


# ============================================================
# CHECK API TOKEN
# ============================================================

if not API_TOKEN:
    raise ValueError(
        "MONDAY_API_TOKEN not found in .env file."
    )


# ============================================================
# FETCH ALL ITEMS
# ============================================================

def fetch_all_items(board_id):
    """
    Fetch all items from a Monday.com board.

    Pagination is handled using Monday.com's cursor.

    For every column we request:
        id
        text
        value
        type

    This is important because Number columns may have:
        text = ""
        value = '{"value":"12345"}'

    Therefore, we cannot rely only on column['text'].
    """

    all_items = []
    cursor = None

    while True:

        # ====================================================
        # FIRST PAGE
        # ====================================================

        if cursor is None:

            query = f"""
            query {{
                boards(ids: [{board_id}]) {{

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
        # API ERRORS
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

                page = (
                    result["data"]
                    ["boards"][0]
                    ["items_page"]
                )

            else:

                page = (
                    result["data"]
                    ["next_items_page"]
                )

        except (
            KeyError,
            TypeError,
            IndexError
        ):

            print("\nUnexpected Monday.com response:")
            print(result)

            return []

        # ====================================================
        # ADD ITEMS
        # ====================================================

        items = page.get("items", [])

        all_items.extend(items)

        # ====================================================
        # NEXT CURSOR
        # ====================================================

        cursor = page.get("cursor")

        if not cursor:
            break

    return all_items


# ============================================================
# EXTRACT COLUMN VALUE
# ============================================================

def extract_column_value(column_name, column):
    """
    Extract the correct value from a Monday.com column.

    Priority:

    1. text
    2. value for Numbers
    3. value for Formula
    4. value for other column types
    5. empty string

    This fixes the problem where:
        Deal Value / numeric fields
        have empty 'text'
        but actual data is inside 'value'.
    """

    text = column.get("text")
    value = column.get("value")
    column_type = column.get("type")

    # ========================================================
    # 1. NORMAL TEXT VALUE
    # ========================================================

    if text is not None:

        text_string = str(text).strip()

        if text_string != "":
            return text

    # ========================================================
    # 2. NUMBER COLUMN
    # ========================================================

    if column_type == "numbers":

        if value is not None:

            try:

                parsed = json.loads(value)

                # Example:
                # {"value":"70000"}

                if isinstance(parsed, dict):

                    number = parsed.get("value")

                    if number is not None:
                        return number

                return parsed

            except (
                json.JSONDecodeError,
                TypeError
            ):

                return value

    # ========================================================
    # 3. FORMULA COLUMN
    # ========================================================

    if column_type == "formula":

        if value is not None:

            try:

                parsed = json.loads(value)

                # Formula may return:
                # {"value":"12345"}

                if isinstance(parsed, dict):

                    result = parsed.get("value")

                    if result is not None:
                        return result

                return parsed

            except (
                json.JSONDecodeError,
                TypeError
            ):

                return value

    # ========================================================
    # 4. OTHER COLUMN TYPES
    # ========================================================

    if value is not None:

        try:

            parsed = json.loads(value)

            if isinstance(parsed, dict):

                # Try common Monday.com keys

                for key in [
                    "value",
                    "text",
                    "display_value"
                ]:

                    if key in parsed:
                        return parsed[key]

                return ""

            return parsed

        except (
            json.JSONDecodeError,
            TypeError
        ):

            return value

    # ========================================================
    # 5. FALLBACK
    # ========================================================

    return text if text is not None else ""


# ============================================================
# SAFE NUMERIC CONVERSION
# ============================================================

def safe_numeric_value(value):
    """
    Convert one Monday.com value into a number.

    Handles:
        100000
        "100000"
        "100,000"
        "₹100000"
        "$100000"
        None
        ""
    """

    if value is None:
        return 0.0

    # Already numeric
    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip()

    if value == "":
        return 0.0

    # Remove common formatting
    value = (
        value
        .replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .strip()
    )

    try:
        return float(value)

    except ValueError:

        # Try extracting numeric part
        import re

        match = re.search(
            r"-?\d+(?:\.\d+)?",
            value
        )

        if match:

            try:
                return float(match.group())

            except ValueError:
                return 0.0

        return 0.0


# ============================================================
# GET WORK ORDERS
# ============================================================

def get_work_orders():
    """
    Fetch and clean Work Orders from Monday.com.

    Returns:
        pandas.DataFrame
    """

    print("\nLoading Work Orders from Monday.com...")

    items = fetch_all_items(BOARD_ID)

    if not items:

        print("No Work Order records found.")

        return pd.DataFrame()

    rows = []

    # ========================================================
    # CONVERT MONDAY ITEMS TO DATAFRAME ROWS
    # ========================================================

    for item in items:

        row = {
            "Deal Name": item.get("name")
        }

        for column in item.get(
            "column_values",
            []
        ):

            column_id = column.get("id")

            column_name = COLUMN_MAPPING.get(
                column_id,
                column_id
            )

            extracted_value = extract_column_value(
                column_name,
                column
            )

            row[column_name] = extracted_value

        rows.append(row)

    # ========================================================
    # CREATE DATAFRAME
    # ========================================================

    df = pd.DataFrame(rows)

    # ========================================================
    # DEBUG
    # ========================================================

    print("\n===== WORK ORDER DATA =====")

    print(
        "Number of records:",
        len(df)
    )

    print(
        "Number of columns:",
        len(df.columns)
    )

    print("\nColumn names:")

    print(
        df.columns.tolist()
    )

    # ========================================================
    # NUMERIC COLUMNS
    # ========================================================

    numeric_columns = [

        "Amount Excl GST",
        "Amount Incl GST",

        "Billed Value Excl GST",
        "Billed Value Incl GST",

        "Collected Amount Incl GST",

        "Amount To Be Billed Excl GST",
        "Amount To Be Billed Incl GST",

        "Amount Receivable",

        "Quantity By Ops",
        "Quantity As Per PO",
        "Quantity Billed",
        "Balance Quantity"
    ]

    # ========================================================
    # CONVERT NUMERIC COLUMNS
    # ========================================================

    for column_name in numeric_columns:

        if column_name in df.columns:

            df[column_name] = (
                df[column_name]
                .apply(safe_numeric_value)
            )

    # ========================================================
    # DEBUG BILLING VALUES
    # ========================================================

    print("\n===== BILLING VALUE CHECK =====")

    billing_debug_columns = [

        "Deal Name",

        "Amount Excl GST",
        "Amount Incl GST",

        "Billed Value Excl GST",
        "Billed Value Incl GST",

        "Collected Amount Incl GST",

        "Amount To Be Billed Excl GST",
        "Amount To Be Billed Incl GST",

        "Amount Receivable"
    ]

    available_debug_columns = [
        column
        for column in billing_debug_columns
        if column in df.columns
    ]

    if available_debug_columns:

        print(
            df[
                available_debug_columns
            ].head(20).to_string(index=False)
        )

    # ========================================================
    # DATA CLEANING
    # ========================================================

    df = clean_dataframe(df)

    # ========================================================
    # RE-CONVERT NUMERIC COLUMNS
    # ========================================================

    for column_name in numeric_columns:

        if column_name in df.columns:

            df[column_name] = (
                df[column_name]
                .apply(safe_numeric_value)
            )

    # ========================================================
    # NORMALIZE EXECUTION STATUS
    # ========================================================

    if "Execution Status" in df.columns:

        df["Execution Status"] = (
            df["Execution Status"]
            .apply(normalize_status)
        )

    # ========================================================
    # NORMALIZE STATUS
    # ========================================================

    if "Status" in df.columns:

        df["Status"] = (
            df["Status"]
            .apply(normalize_status)
        )

    # ========================================================
    # NORMALIZE SECTOR
    # ========================================================

    if "Sector" in df.columns:

        df["Sector"] = (
            df["Sector"]
            .apply(normalize_sector)
        )

    # ========================================================
    # NORMALIZE DATES
    # ========================================================

    date_columns = [

        "Date",

        "Data Delivery Date",

        "Date of PO/LOI",

        "Probable Start Date",

        "Probable End Date",

        "Last Invoice Date",

        "Collection Date"
    ]

    df = normalize_dates(
        df,
        date_columns
    )

    # ========================================================
    # FINAL BILLING CHECK
    # ========================================================

    print("\n===== FINAL BILLING CHECK =====")

    final_billing_columns = [

        "Deal Name",

        "Billed Value Incl GST",

        "Collected Amount Incl GST",

        "Amount Receivable",

        "Amount To Be Billed Incl GST"
    ]

    available_final_columns = [

        column
        for column in final_billing_columns
        if column in df.columns
    ]

    if available_final_columns:

        print(
            df[
                available_final_columns
            ].head(20).to_string(index=False)
        )

    # ========================================================
    # TOTALS
    # ========================================================

    print("\n===== WORK ORDER TOTALS =====")

    if "Billed Value Incl GST" in df.columns:

        print(
            "Total Billed Value Incl GST:",
            df["Billed Value Incl GST"].sum()
        )

    if "Collected Amount Incl GST" in df.columns:

        print(
            "Total Collected Amount Incl GST:",
            df["Collected Amount Incl GST"].sum()
        )

    if "Amount Receivable" in df.columns:

        print(
            "Total Amount Receivable:",
            df["Amount Receivable"].sum()
        )

    if "Amount To Be Billed Incl GST" in df.columns:

        print(
            "Total Amount To Be Billed Incl GST:",
            df["Amount To Be Billed Incl GST"].sum()
        )

    return df


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    df = get_work_orders()

    print("\n===== WORK ORDERS DATA =====")

    print(
        "Number of records:",
        len(df)
    )

    print(
        "Number of columns:",
        len(df.columns)
    )

    print("\nColumn names:")

    print(
        df.columns.tolist()
    )

    print("\nFirst 5 records:")

    print(
        df.head().to_string(index=False)
    )