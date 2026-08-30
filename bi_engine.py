import pandas as pd

# ============================================================
# IMPORT APIS
# ============================================================

from deals_api import get_deals
from monday_api import get_work_orders


# ============================================================
# SAFE NUMERIC CONVERSION
# ============================================================

def safe_numeric(series):
    """
    Convert values to numeric.

    Handles:
    - None
    - NaN
    - empty strings
    - commas
    - currency symbols
    - invalid values
    """

    if series is None:
        return pd.Series(dtype=float)

    cleaned = (
        series
        .astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("€", "", regex=False)
        .str.replace("£", "", regex=False)
    )

    return pd.to_numeric(
        cleaned,
        errors="coerce"
    ).fillna(0.0)


# ============================================================
# SAFE COLUMN GETTER
# ============================================================

def get_column(df, column_name, default=0.0):
    """
    Safely get a dataframe column.
    """

    if df is None or df.empty:
        return pd.Series(dtype=float)

    if column_name not in df.columns:
        return pd.Series(
            default,
            index=df.index,
            dtype=float
        )

    return safe_numeric(df[column_name])


# ============================================================
# LOAD BI DATA
# ============================================================

def load_bi_data():
    """
    Load Deals and Work Orders.

    Used by ai_agent.py.
    """

    print("\n==============================================")
    print("        LOADING BI DATA")
    print("==============================================\n")

    # --------------------------------------------------------
    # DEALS
    # --------------------------------------------------------

    print("Loading Deals from Monday.com...")

    try:
        deals = get_deals()
    except Exception as e:
        print("\nERROR loading Deals:")
        print(e)
        deals = pd.DataFrame()

    # --------------------------------------------------------
    # WORK ORDERS
    # --------------------------------------------------------

    print("\nLoading Work Orders from Monday.com...")

    try:
        work_orders = get_work_orders()
    except Exception as e:
        print("\nERROR loading Work Orders:")
        print(e)
        work_orders = pd.DataFrame()

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print("\n===== DATA LOADED =====")
    print(f"Deals: {len(deals)}")
    print(f"Work Orders: {len(work_orders)}")

    return deals, work_orders


# ============================================================
# DEAL PIPELINE SUMMARY
# ============================================================

def pipeline_summary(deals):

    if deals is None or deals.empty:
        return {
            "total_deals": 0,
            "total_pipeline": 0.0,
            "forecast_value": 0.0
        }

    deal_values = get_column(
        deals,
        "Deal Value"
    )

    if "Calculated Forecast Value" in deals.columns:

        forecast_values = safe_numeric(
            deals["Calculated Forecast Value"]
        )

    else:

        forecast_values = get_column(
            deals,
            "Forecast Value"
        )

    return {
        "total_deals": int(len(deals)),
        "total_pipeline": float(deal_values.sum()),
        "forecast_value": float(forecast_values.sum())
    }


# ============================================================
# PIPELINE BY SECTOR
# ============================================================

def pipeline_by_sector(deals):

    if deals is None or deals.empty:

        return pd.DataFrame(
            columns=[
                "Sector",
                "Deals",
                "Pipeline",
                "Forecast"
            ]
        )

    temp = deals.copy()

    # --------------------------------------------------------
    # Sector
    # --------------------------------------------------------

    if "Sector" not in temp.columns:
        temp["Sector"] = "Unknown"

    temp["Sector"] = (
        temp["Sector"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    temp.loc[
        temp["Sector"].isin(
            ["", "nan", "None"]
        ),
        "Sector"
    ] = "Unknown"

    # --------------------------------------------------------
    # Deal Value
    # --------------------------------------------------------

    temp["Deal Value"] = get_column(
        temp,
        "Deal Value"
    )

    # --------------------------------------------------------
    # Forecast
    # --------------------------------------------------------

    if "Calculated Forecast Value" in temp.columns:

        temp["Forecast Value"] = safe_numeric(
            temp["Calculated Forecast Value"]
        )

    else:

        temp["Forecast Value"] = get_column(
            temp,
            "Forecast Value"
        )

    # --------------------------------------------------------
    # Group
    # --------------------------------------------------------

    result = (
        temp
        .groupby(
            "Sector",
            dropna=False
        )
        .agg(
            Deals=("Deal Name", "count"),
            Pipeline=("Deal Value", "sum"),
            Forecast=("Forecast Value", "sum")
        )
        .reset_index()
    )

    return result.sort_values(
        by="Pipeline",
        ascending=False
    )


# ============================================================
# SPECIFIC SECTOR PIPELINE
# ============================================================

def sector_pipeline(deals, sector_name):

    if deals is None or deals.empty:

        return {
            "sector": sector_name,
            "deals": 0,
            "pipeline": 0.0,
            "forecast": 0.0
        }

    if "Sector" not in deals.columns:

        return {
            "sector": sector_name,
            "deals": 0,
            "pipeline": 0.0,
            "forecast": 0.0
        }

    temp = deals.copy()

    temp["_sector_normalized"] = (
        temp["Sector"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    target = (
        str(sector_name)
        .strip()
        .lower()
    )

    filtered = temp[
        temp["_sector_normalized"] == target
    ].copy()

    filtered["Deal Value"] = get_column(
        filtered,
        "Deal Value"
    )

    if "Calculated Forecast Value" in filtered.columns:

        filtered["Forecast Value"] = safe_numeric(
            filtered["Calculated Forecast Value"]
        )

    else:

        filtered["Forecast Value"] = get_column(
            filtered,
            "Forecast Value"
        )

    return {
        "sector": sector_name,
        "deals": int(len(filtered)),
        "pipeline": float(
            filtered["Deal Value"].sum()
        ),
        "forecast": float(
            filtered["Forecast Value"].sum()
        )
    }


# ============================================================
# MINING PIPELINE
# ============================================================

def mining_pipeline(deals):

    return sector_pipeline(
        deals,
        "Mining"
    )


# ============================================================
# WORK ORDER SUMMARY
# ============================================================

def work_order_summary(work_orders):

    if work_orders is None or work_orders.empty:

        return {
            "total_work_orders": 0,
            "billed": 0.0,
            "collected": 0.0,
            "receivable": 0.0
        }

    billed = get_column(
        work_orders,
        "Billed Value Incl GST"
    ).sum()

    collected = get_column(
        work_orders,
        "Collected Amount Incl GST"
    ).sum()

    if "Amount Receivable" in work_orders.columns:

        receivable = get_column(
            work_orders,
            "Amount Receivable"
        ).sum()

    else:

        receivable = billed - collected

    return {
        "total_work_orders": int(
            len(work_orders)
        ),
        "billed": float(billed),
        "collected": float(collected),
        "receivable": float(receivable)
    }


# ============================================================
# BILLING SUMMARY
# ============================================================

def billing_summary(work_orders):

    if work_orders is None or work_orders.empty:

        return {
            "billed_value": 0.0,
            "collected_amount": 0.0,
            "receivable": 0.0,
            "to_be_billed": 0.0
        }

    billed = get_column(
        work_orders,
        "Billed Value Incl GST"
    ).sum()

    collected = get_column(
        work_orders,
        "Collected Amount Incl GST"
    ).sum()

    if "Amount Receivable" in work_orders.columns:

        receivable = get_column(
            work_orders,
            "Amount Receivable"
        ).sum()

    else:

        receivable = billed - collected

    to_be_billed = get_column(
        work_orders,
        "Amount To Be Billed Incl GST"
    ).sum()

    return {
        "billed_value": float(billed),
        "collected_amount": float(collected),
        "receivable": float(receivable),
        "to_be_billed": float(to_be_billed)
    }


# ============================================================
# BILLING SUMMARY EXCLUDING GST
# ============================================================

def billing_summary_excl_gst(work_orders):

    if work_orders is None or work_orders.empty:

        return {
            "billed_value": 0.0,
            "to_be_billed": 0.0
        }

    billed = get_column(
        work_orders,
        "Billed Value Excl GST"
    ).sum()

    to_be_billed = get_column(
        work_orders,
        "Amount To Be Billed Excl GST"
    ).sum()

    return {
        "billed_value": float(billed),
        "to_be_billed": float(to_be_billed)
    }


# ============================================================
# WORK ORDER BY SECTOR
# ============================================================

def work_order_by_sector(work_orders):

    if work_orders is None or work_orders.empty:

        return pd.DataFrame(
            columns=[
                "Sector",
                "Work Orders",
                "Billed",
                "Collected",
                "Receivable"
            ]
        )

    temp = work_orders.copy()

    if "Sector" not in temp.columns:
        temp["Sector"] = "Unknown"

    temp["Sector"] = (
        temp["Sector"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    temp.loc[
        temp["Sector"].isin(
            ["", "nan", "None"]
        ),
        "Sector"
    ] = "Unknown"

    temp["Billed"] = get_column(
        temp,
        "Billed Value Incl GST"
    )

    temp["Collected"] = get_column(
        temp,
        "Collected Amount Incl GST"
    )

    temp["Receivable"] = get_column(
        temp,
        "Amount Receivable"
    )

    result = (
        temp
        .groupby("Sector")
        .agg(
            **{
                "Work Orders": (
                    "Deal Name",
                    "count"
                ),
                "Billed": (
                    "Billed",
                    "sum"
                ),
                "Collected": (
                    "Collected",
                    "sum"
                ),
                "Receivable": (
                    "Receivable",
                    "sum"
                )
            }
        )
        .reset_index()
    )

    return result.sort_values(
        by="Billed",
        ascending=False
    )


# ============================================================
# DATA QUALITY
# ============================================================

def data_quality(df):

    if df is None or df.empty:

        return {
            "records": 0,
            "columns": 0,
            "missing_cells": 0
        }

    return {
        "records": int(len(df)),
        "columns": int(len(df.columns)),
        "missing_cells": int(
            df.isna().sum().sum()
        )
    }


# ============================================================
# NON-ZERO DEALS
# ============================================================

def show_non_zero_deals(deals):

    if deals is None or deals.empty:

        print("\n===== NON-ZERO DEALS =====")
        print("No deals found.")

        return

    temp = deals.copy()

    temp["Deal Value"] = get_column(
        temp,
        "Deal Value"
    )

    if "Close Probability" in temp.columns:

        temp["Close Probability"] = safe_numeric(
            temp["Close Probability"]
        )

    else:

        temp["Close Probability"] = 0.0

    if "Calculated Forecast Value" in temp.columns:

        temp["Calculated Forecast Value"] = safe_numeric(
            temp["Calculated Forecast Value"]
        )

    else:

        temp["Calculated Forecast Value"] = (
            temp["Deal Value"]
            *
            temp["Close Probability"]
            /
            100
        )

    non_zero = temp[
        temp["Deal Value"] > 0
    ].copy()

    print("\n===== NON-ZERO DEALS =====")

    if non_zero.empty:

        print("No non-zero deal values found.")

        return

    columns = [
        "Deal Name",
        "Deal Value",
        "Close Probability",
        "Calculated Forecast Value"
    ]

    if "Sector" in non_zero.columns:
        columns.append("Sector")

    print(
        non_zero[columns].to_string(
            index=False
        )
    )


# ============================================================
# DEAL VALUE CHECK
# ============================================================

def deal_value_check(deals):

    if deals is None or deals.empty:

        print("\n===== DEAL VALUE TOTAL =====")
        print("Total Deal Value: 0.0")

        return

    values = get_column(
        deals,
        "Deal Value"
    )

    if "Calculated Forecast Value" in deals.columns:

        forecast = get_column(
            deals,
            "Calculated Forecast Value"
        )

    else:

        forecast = get_column(
            deals,
            "Forecast Value"
        )

    print("\n===== DEAL VALUE TOTAL =====")

    print(
        "Total Deal Value:",
        float(values.sum())
    )

    print(
        "Non-zero Deal Values:",
        int((values > 0).sum())
    )

    print("\n===== FORECAST VALUE TOTAL =====")

    print(
        "Total Forecast Value:",
        float(forecast.sum())
    )

    print(
        "Non-zero Forecast Values:",
        int((forecast > 0).sum())
    )


# ============================================================
# MAIN BI ENGINE
# ============================================================

def main():

    print(
        "\n=============================================="
    )

    print(
        "        SKYLARK BI AGENT"
    )

    print(
        "=============================================="
    )

    # ========================================================
    # LOAD WORK ORDERS
    # ========================================================

    print(
        "\nLoading Work Orders from Monday.com..."
    )

    try:

        work_orders = get_work_orders()

    except Exception as e:

        print("\nERROR loading Work Orders:")
        print(e)

        work_orders = pd.DataFrame()

    # ========================================================
    # LOAD DEALS
    # ========================================================

    print(
        "\nLoading Deals from Monday.com..."
    )

    try:

        deals = get_deals()

    except Exception as e:

        print("\nERROR loading Deals:")
        print(e)

        deals = pd.DataFrame()

    # ========================================================
    # WORK ORDER DATA
    # ========================================================

    print("\n===== WORK ORDER DATA =====")

    print(
        "Number of records:",
        len(work_orders)
    )

    print(
        "Number of columns:",
        len(work_orders.columns)
    )

    if not work_orders.empty:

        print("\nColumn names:")

        print(
            work_orders.columns.tolist()
        )

    # ========================================================
    # DEAL DATA
    # ========================================================

    print("\n===== DEAL DATA =====")

    print(
        "Number of records:",
        len(deals)
    )

    print(
        "Number of columns:",
        len(deals.columns)
    )

    if not deals.empty:

        print("\nDeal columns:")

        print(
            deals.columns.tolist()
        )

    # ========================================================
    # DEAL CHECK
    # ========================================================

    show_non_zero_deals(
        deals
    )

    deal_value_check(
        deals
    )

    # ========================================================
    # DATA SUMMARY
    # ========================================================

    print("\n===== DATA SUMMARY =====")

    print(
        "Work Orders:",
        len(work_orders)
    )

    print(
        "Deals:",
        len(deals)
    )

    # ========================================================
    # PIPELINE SUMMARY
    # ========================================================

    pipeline = pipeline_summary(
        deals
    )

    print("\n===== PIPELINE SUMMARY =====")

    print(
        "Total Deals:",
        pipeline["total_deals"]
    )

    print(
        "Total Pipeline:",
        pipeline["total_pipeline"]
    )

    print(
        "Forecast Value:",
        pipeline["forecast_value"]
    )

    # ========================================================
    # MINING PIPELINE
    # ========================================================

    mining = mining_pipeline(
        deals
    )

    print("\n===== MINING PIPELINE =====")

    print(mining)

    # ========================================================
    # PIPELINE BY SECTOR
    # ========================================================

    sector_pipeline_df = pipeline_by_sector(
        deals
    )

    print("\n===== PIPELINE BY SECTOR =====")

    if sector_pipeline_df.empty:

        print(
            "No sector data available."
        )

    else:

        print(
            sector_pipeline_df.to_string(
                index=False
            )
        )

    # ========================================================
    # WORK ORDER SUMMARY
    # ========================================================

    wo_summary = work_order_summary(
        work_orders
    )

    print("\n===== WORK ORDER SUMMARY =====")

    print(
        "Total Work Orders:",
        wo_summary["total_work_orders"]
    )

    print(
        "Billed:",
        wo_summary["billed"]
    )

    print(
        "Collected:",
        wo_summary["collected"]
    )

    print(
        "Receivable:",
        wo_summary["receivable"]
    )

    # ========================================================
    # BILLING SUMMARY
    # ========================================================

    billing = billing_summary(
        work_orders
    )

    print("\n===== BILLING SUMMARY =====")

    print(
        "Billed Value:",
        billing["billed_value"]
    )

    print(
        "Collected Amount:",
        billing["collected_amount"]
    )

    print(
        "Receivable:",
        billing["receivable"]
    )

    print(
        "To Be Billed:",
        billing["to_be_billed"]
    )

    # ========================================================
    # WORK ORDER BY SECTOR
    # ========================================================

    wo_sector = work_order_by_sector(
        work_orders
    )

    print("\n===== WORK ORDER BY SECTOR =====")

    if wo_sector.empty:

        print(
            "No Work Order sector data available."
        )

    else:

        print(
            wo_sector.to_string(
                index=False
            )
        )

    # ========================================================
    # DATA QUALITY
    # ========================================================

    print("\n===== DATA QUALITY =====")

    print(
        "Deals:",
        data_quality(deals)
    )

    print(
        "Work Orders:",
        data_quality(work_orders)
    )

    # ========================================================
    # END
    # ========================================================

    print(
        "\n=============================================="
    )

    print(
        "        BI ENGINE COMPLETED"
    )

    print(
        "==============================================\n"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()