import pandas as pd
import re


def clean_text(value):
    """Clean text values while preserving missing data."""

    if pd.isna(value):
        return None

    value = str(value).strip()

    if value == "":
        return None

    # Normalize multiple spaces
    value = re.sub(r"\s+", " ", value)

    return value


def clean_dataframe(df):
    """General cleaning for Monday.com data."""

    df = df.copy()

    # ------------------------------------------------
    # 1. Clean column names
    # ------------------------------------------------

    df.columns = (
        df.columns
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    # ------------------------------------------------
    # 2. Clean text values
    # ------------------------------------------------

    for column in df.columns:

        if df[column].dtype == "object":

            df[column] = df[column].apply(clean_text)

    # ------------------------------------------------
    # 3. Normalize common missing values
    # ------------------------------------------------

    missing_values = [
        "",
        "None",
        "none",
        "NULL",
        "null",
        "N/A",
        "n/a",
        "NA",
        "na",
        "-"
    ]

    for column in df.columns:

        if df[column].dtype == "object":

            df[column] = df[column].replace(
                missing_values,
                None
            )

    return df


def normalize_status(value):

    if value is None:
        return None

    value = str(value).strip().lower()

    status_map = {
        "open": "Open",
        "opened": "Open",
        "closed": "Closed",
        "complete": "Completed",
        "completed": "Completed",
        "pending": "Pending",
        "in progress": "In Progress",
        "wip": "In Progress"
    }

    return status_map.get(value, str(value).strip().title())


def normalize_sector(value):

    if value is None:
        return None

    value = str(value).strip()

    sector_map = {
        "mining": "Mining",
        "powerline": "Powerline",
        "power": "Power",
        "energy": "Energy",
        "renewable energy": "Energy"
    }

    return sector_map.get(
        value.lower(),
        value.title()
    )


def normalize_dates(df, date_columns):

    df = df.copy()

    for column in date_columns:

        if column not in df.columns:
            continue

        # Convert values to strings first
        values = df[column].astype("string").str.strip()

        # Treat empty values as missing
        values = values.replace(
            ["", "None", "none", "NULL", "null"],
            pd.NA
        )

        # Parse dates
        df[column] = pd.to_datetime(
            values,
            errors="coerce",
            utc=True,
            format="mixed"
        )

    return df

def get_data_quality_report(df):

    report = []

    for column in df.columns:

        missing_count = df[column].isna().sum()

        total_count = len(df)

        missing_percentage = (
            missing_count / total_count * 100
            if total_count > 0
            else 0
        )

        report.append({
            "Column": column,
            "Missing": missing_count,
            "Missing %": round(
                missing_percentage,
                2
            )
        })

    return pd.DataFrame(report)