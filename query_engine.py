# ============================================================
# SKYLARK BI AGENT - QUERY ENGINE
# ============================================================

import pandas as pd
import importlib


# ============================================================
# LOAD DEALS
# ============================================================

from deals_api import get_deals


# ============================================================
# LOAD WORK ORDERS
# ============================================================

def load_work_orders():
    """
    Load Work Order data from the existing project.

    We try the common module names so that
    query_engine.py does not depend on a file named
    work_orders_api.py.
    """

    possible_modules = [
        "work_order_api",
        "work_orders",
        "work_order",
        "work_orders_data",
        "data_loader",
        "bi_engine",
    ]

    possible_functions = [
        "get_work_orders",
        "load_work_orders",
        "fetch_work_orders",
    ]

    for module_name in possible_modules:

        try:
            module = importlib.import_module(module_name)

        except ImportError:
            continue

        for function_name in possible_functions:

            function = getattr(
                module,
                function_name,
                None
            )

            if callable(function):

                try:
                    result = function()

                    if isinstance(result, pd.DataFrame):
                        return result

                except Exception as e:
                    print(
                        f"Could not load work orders from "
                        f"{module_name}.{function_name}: {e}"
                    )

    print(
        "\nWARNING: Could not automatically find "
        "the Work Order loader."
    )

    print(
        "Deals can still be queried."
    )

    return pd.DataFrame()


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print("\n==============================================")
    print("        LOADING BI DATA")
    print("==============================================")

    # --------------------------------------------------------
    # Deals
    # --------------------------------------------------------

    try:

        deals_df = get_deals()

    except Exception as e:

        print("\nError loading Deals:")
        print(e)

        deals_df = pd.DataFrame()

    # --------------------------------------------------------
    # Work Orders
    # --------------------------------------------------------

    work_orders_df = load_work_orders()

    print("\n===== DATA LOADED =====")

    print(
        "Deals:",
        len(deals_df)
    )

    print(
        "Work Orders:",
        len(work_orders_df)
    )

    return deals_df, work_orders_df


# ============================================================
# SAFE NUMBER
# ============================================================

def safe_number(series):

    return pd.to_numeric(
        series,
        errors="coerce"
    ).fillna(0)


# ============================================================
# DEAL SUMMARY
# ============================================================

def deal_summary(df):

    if df.empty:

        return {
            "total_deals": 0,
            "pipeline": 0.0,
            "forecast": 0.0
        }

    total_deals = len(df)

    pipeline = 0.0

    forecast = 0.0

    if "Deal Value" in df.columns:

        pipeline = safe_number(
            df["Deal Value"]
        ).sum()

    if "Calculated Forecast Value" in df.columns:

        forecast = safe_number(
            df["Calculated Forecast Value"]
        ).sum()

    elif "Forecast Value" in df.columns:

        forecast = safe_number(
            df["Forecast Value"]
        ).sum()

    return {
        "total_deals": total_deals,
        "pipeline": float(pipeline),
        "forecast": float(forecast)
    }


# ============================================================
# WORK ORDER SUMMARY
# ============================================================

def work_order_summary(df):

    if df.empty:

        return {
            "total_work_orders": 0,
            "billed": 0.0,
            "collected": 0.0,
            "receivable": 0.0,
            "to_be_billed": 0.0
        }

    result = {
        "total_work_orders": len(df),
        "billed": 0.0,
        "collected": 0.0,
        "receivable": 0.0,
        "to_be_billed": 0.0
    }

    if "Billed Value Incl GST" in df.columns:

        result["billed"] = float(
            safe_number(
                df["Billed Value Incl GST"]
            ).sum()
        )

    if "Collected Amount Incl GST" in df.columns:

        result["collected"] = float(
            safe_number(
                df["Collected Amount Incl GST"]
            ).sum()
        )

    if "Amount Receivable" in df.columns:

        result["receivable"] = float(
            safe_number(
                df["Amount Receivable"]
            ).sum()
        )

    if "Amount To Be Billed Incl GST" in df.columns:

        result["to_be_billed"] = float(
            safe_number(
                df["Amount To Be Billed Incl GST"]
            ).sum()
        )

    return result


# ============================================================
# PIPELINE BY SECTOR
# ============================================================

def pipeline_by_sector(df):

    if df.empty:

        return pd.DataFrame()

    if "Sector" not in df.columns:

        return pd.DataFrame()

    temp = df.copy()

    temp["Sector"] = (
        temp["Sector"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    temp.loc[
        temp["Sector"] == "",
        "Sector"
    ] = "Unknown"

    if "Deal Value" in temp.columns:

        temp["Deal Value"] = safe_number(
            temp["Deal Value"]
        )

    else:

        temp["Deal Value"] = 0.0

    if "Calculated Forecast Value" in temp.columns:

        temp["Calculated Forecast Value"] = safe_number(
            temp["Calculated Forecast Value"]
        )

    elif "Forecast Value" in temp.columns:

        temp["Calculated Forecast Value"] = safe_number(
            temp["Forecast Value"]
        )

    else:

        temp["Calculated Forecast Value"] = 0.0

    result = (
        temp
        .groupby("Sector")
        .agg(
            Deals=("Deal Name", "count"),
            Pipeline=("Deal Value", "sum"),
            Forecast=("Calculated Forecast Value", "sum")
        )
        .reset_index()
    )

    result = result.sort_values(
        "Pipeline",
        ascending=False
    )

    return result


# ============================================================
# WORK ORDER BY SECTOR
# ============================================================

def work_order_by_sector(df):

    if df.empty:

        return pd.DataFrame()

    if "Sector" not in df.columns:

        return pd.DataFrame()

    temp = df.copy()

    temp["Sector"] = (
        temp["Sector"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    temp.loc[
        temp["Sector"] == "",
        "Sector"
    ] = "Unknown"

    # --------------------------------------------------------
    # Numeric columns
    # --------------------------------------------------------

    numeric_columns = [
        "Billed Value Incl GST",
        "Collected Amount Incl GST",
        "Amount Receivable"
    ]

    for column in numeric_columns:

        if column in temp.columns:

            temp[column] = safe_number(
                temp[column]
            )

        else:

            temp[column] = 0.0

    result = (
        temp
        .groupby("Sector")
        .agg(
            Work_Orders=("Deal Name", "count"),
            Billed=("Billed Value Incl GST", "sum"),
            Collected=("Collected Amount Incl GST", "sum"),
            Receivable=("Amount Receivable", "sum")
        )
        .reset_index()
    )

    result = result.sort_values(
        "Billed",
        ascending=False
    )

    return result


# ============================================================
# SEARCH DEALS
# ============================================================

def search_deals(df, keyword):

    if df.empty:

        return pd.DataFrame()

    keyword = str(
        keyword
    ).strip().lower()

    if keyword == "":

        return pd.DataFrame()

    mask = pd.Series(
        False,
        index=df.index
    )

    # --------------------------------------------------------
    # Search Deal Name
    # --------------------------------------------------------

    if "Deal Name" in df.columns:

        mask |= (
            df["Deal Name"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.contains(
                keyword,
                na=False
            )
        )

    # --------------------------------------------------------
    # Search Client Code
    # --------------------------------------------------------

    if "Client Code" in df.columns:

        mask |= (
            df["Client Code"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.contains(
                keyword,
                na=False
            )
        )

    # --------------------------------------------------------
    # Search Sector
    # --------------------------------------------------------

    if "Sector" in df.columns:

        mask |= (
            df["Sector"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.contains(
                keyword,
                na=False
            )
        )

    return df[mask]


# ============================================================
# SEARCH WORK ORDERS
# ============================================================

def search_work_orders(df, keyword):

    if df.empty:

        return pd.DataFrame()

    keyword = str(
        keyword
    ).strip().lower()

    if keyword == "":

        return pd.DataFrame()

    mask = pd.Series(
        False,
        index=df.index
    )

    search_columns = [
        "Deal Name",
        "Customer Name Code",
        "Serial Number",
        "Nature of Work",
        "Sector",
        "Assigned Person",
        "BD/KAM Personnel Code",
        "Execution Status",
        "Invoice Status",
        "Collection Status",
        "Billing Status"
    ]

    for column in search_columns:

        if column in df.columns:

            mask |= (
                df[column]
                .fillna("")
                .astype(str)
                .str.lower()
                .str.contains(
                    keyword,
                    na=False
                )
            )

    return df[mask]


# ============================================================
# DEAL DETAILS
# ============================================================

def show_deal_details(df, keyword):

    result = search_deals(
        df,
        keyword
    )

    if result.empty:

        print(
            f"\nNo deals found for: {keyword}"
        )

        return

    print(
        f"\n===== DEALS MATCHING '{keyword}' ====="
    )

    columns = [
        "Deal Name",
        "Deal Value",
        "Close Probability",
        "Calculated Forecast Value",
        "Sector",
        "Deal Stage",
        "Deal Owner",
        "Expected Close Date"
    ]

    existing = [
        column
        for column in columns
        if column in result.columns
    ]

    print(
        result[existing]
        .to_string(index=False)
    )


# ============================================================
# WORK ORDER DETAILS
# ============================================================

def show_work_order_details(
    df,
    keyword
):

    result = search_work_orders(
        df,
        keyword
    )

    if result.empty:

        print(
            f"\nNo work orders found for: {keyword}"
        )

        return

    print(
        f"\n===== WORK ORDERS MATCHING '{keyword}' ====="
    )

    columns = [
        "Deal Name",
        "Customer Name Code",
        "Sector",
        "Status",
        "Execution Status",
        "Amount Incl GST",
        "Billed Value Incl GST",
        "Collected Amount Incl GST",
        "Amount Receivable",
        "Amount To Be Billed Incl GST",
        "Billing Status",
        "Collection Status"
    ]

    existing = [
        column
        for column in columns
        if column in result.columns
    ]

    print(
        result[existing]
        .to_string(index=False)
    )


# ============================================================
# OVERALL SUMMARY
# ============================================================

def overall_summary(
    deals_df,
    work_orders_df
):

    deals = deal_summary(
        deals_df
    )

    work_orders = work_order_summary(
        work_orders_df
    )

    print(
        "\n=============================================="
    )

    print(
        "             OVERALL SUMMARY"
    )

    print(
        "=============================================="
    )

    print(
        "\nDEALS"
    )

    print(
        "Total Deals:",
        deals["total_deals"]
    )

    print(
        "Pipeline:",
        deals["pipeline"]
    )

    print(
        "Forecast:",
        deals["forecast"]
    )

    print(
        "\nWORK ORDERS"
    )

    print(
        "Total Work Orders:",
        work_orders["total_work_orders"]
    )

    print(
        "Billed:",
        work_orders["billed"]
    )

    print(
        "Collected:",
        work_orders["collected"]
    )

    print(
        "Receivable:",
        work_orders["receivable"]
    )

    print(
        "To Be Billed:",
        work_orders["to_be_billed"]
    )


# ============================================================
# MENU
# ============================================================

def print_menu():

    print(
        "\n=============================================="
    )

    print(
        "             SKYLARK QUERY ENGINE"
    )

    print(
        "=============================================="
    )

    print(
        "\n1. Overall summary"
    )

    print(
        "2. Pipeline by sector"
    )

    print(
        "3. Work orders by sector"
    )

    print(
        "4. Search deals"
    )

    print(
        "5. Search work orders"
    )

    print(
        "6. Show deal columns"
    )

    print(
        "7. Show work order columns"
    )

    print(
        "0. Exit"
    )


# ============================================================
# INTERACTIVE ENGINE
# ============================================================

def run_query_engine():

    deals_df, work_orders_df = load_data()

    while True:

        print_menu()

        choice = input(
            "\nEnter your choice: "
        ).strip()

        # ----------------------------------------------------
        # Overall
        # ----------------------------------------------------

        if choice == "1":

            overall_summary(
                deals_df,
                work_orders_df
            )

        # ----------------------------------------------------
        # Deal sector
        # ----------------------------------------------------

        elif choice == "2":

            result = pipeline_by_sector(
                deals_df
            )

            if result.empty:

                print(
                    "\nNo deal sector data available."
                )

            else:

                print(
                    "\n===== PIPELINE BY SECTOR ====="
                )

                print(
                    result.to_string(
                        index=False
                    )
                )

        # ----------------------------------------------------
        # Work order sector
        # ----------------------------------------------------

        elif choice == "3":

            result = work_order_by_sector(
                work_orders_df
            )

            if result.empty:

                print(
                    "\nNo work order sector data available."
                )

            else:

                print(
                    "\n===== WORK ORDER BY SECTOR ====="
                )

                print(
                    result.to_string(
                        index=False
                    )
                )

        # ----------------------------------------------------
        # Search deals
        # ----------------------------------------------------

        elif choice == "4":

            keyword = input(
                "\nEnter deal/customer/sector to search: "
            )

            show_deal_details(
                deals_df,
                keyword
            )

        # ----------------------------------------------------
        # Search work orders
        # ----------------------------------------------------

        elif choice == "5":

            keyword = input(
                "\nEnter deal/customer/sector to search: "
            )

            show_work_order_details(
                work_orders_df,
                keyword
            )

        # ----------------------------------------------------
        # Deal columns
        # ----------------------------------------------------

        elif choice == "6":

            print(
                "\n===== DEAL COLUMNS ====="
            )

            if deals_df.empty:

                print(
                    "No Deals data."
                )

            else:

                for index, column in enumerate(
                    deals_df.columns,
                    start=1
                ):

                    print(
                        f"{index}. {column}"
                    )

        # ----------------------------------------------------
        # Work order columns
        # ----------------------------------------------------

        elif choice == "7":

            print(
                "\n===== WORK ORDER COLUMNS ====="
            )

            if work_orders_df.empty:

                print(
                    "No Work Order data."
                )

            else:

                for index, column in enumerate(
                    work_orders_df.columns,
                    start=1
                ):

                    print(
                        f"{index}. {column}"
                    )

        # ----------------------------------------------------
        # Exit
        # ----------------------------------------------------

        elif choice == "0":

            print(
                "\nExiting Query Engine..."
            )

            break

        # ----------------------------------------------------
        # Invalid
        # ----------------------------------------------------

        else:

            print(
                "\nInvalid choice."
            )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    run_query_engine()