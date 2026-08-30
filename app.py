import streamlit as st
import pandas as pd

from bi_engine import load_bi_data


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Skylark BI Agent",
    page_icon="📊",
    layout="wide"
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 40px;
        font-weight: 700;
    }

    .sub-title {
        color: #666;
        font-size: 18px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# LOAD BI DATA
# ============================================================

@st.cache_data(ttl=300)
def get_data():

    data = load_bi_data()

    # Dictionary return
    if isinstance(data, dict):

        deals_df = data.get("deals")
        work_orders_df = data.get("work_orders")

    # Tuple/list return
    elif isinstance(data, (tuple, list)) and len(data) >= 2:

        deals_df = data[0]
        work_orders_df = data[1]

    else:

        raise ValueError(
            "load_bi_data() must return "
            "(deals, work_orders) or "
            "{'deals': ..., 'work_orders': ...}"
        )

    if deals_df is None:
        raise ValueError("Deals data was not returned.")

    if work_orders_df is None:
        raise ValueError("Work Orders data was not returned.")

    if not isinstance(deals_df, pd.DataFrame):
        deals_df = pd.DataFrame(deals_df)

    if not isinstance(work_orders_df, pd.DataFrame):
        work_orders_df = pd.DataFrame(work_orders_df)

    return deals_df.copy(), work_orders_df.copy()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def money(value):

    try:
        value = float(value)

        return f"₹{value:,.2f}"

    except Exception:
        return "₹0.00"


def number(value):

    try:
        return f"{int(value):,}"

    except Exception:
        return "0"


def find_column(df, possible_names):

    normalized = {
        str(col).strip().lower(): col
        for col in df.columns
    }

    for name in possible_names:

        key = str(name).strip().lower()

        if key in normalized:
            return normalized[key]

    return None


def numeric_sum(df, column):

    if column is None:
        return 0

    return (
        pd.to_numeric(
            df[column],
            errors="coerce"
        )
        .fillna(0)
        .sum()
    )


def search_dataframe(df, search):

    if not search:
        return df.copy()

    search = str(search).strip()

    if not search:
        return df.copy()

    mask = pd.Series(
        False,
        index=df.index
    )

    for col in df.columns:

        mask = (
            mask
            |
            df[col]
            .astype(str)
            .str.contains(
                search,
                case=False,
                na=False,
                regex=False
            )
        )

    return df[mask]


# ============================================================
# LOAD DATA
# ============================================================

try:

    with st.spinner("Loading BI data..."):

        deals_df, work_orders_df = get_data()

except Exception as e:

    st.error("Unable to load BI data.")

    st.exception(e)

    st.stop()


# ============================================================
# COLUMN DETECTION
# ============================================================

deal_name_col = find_column(
    deals_df,
    ["Deal Name"]
)

deal_value_col = find_column(
    deals_df,
    ["Deal Value"]
)

deal_sector_col = find_column(
    deals_df,
    ["Sector"]
)

forecast_col = find_column(
    deals_df,
    [
        "Calculated Forecast Value",
        "Forecast Value"
    ]
)

wo_deal_col = find_column(
    work_orders_df,
    ["Deal Name"]
)

wo_sector_col = find_column(
    work_orders_df,
    ["Sector"]
)

billed_col = find_column(
    work_orders_df,
    ["Billed Value Incl GST"]
)

collected_col = find_column(
    work_orders_df,
    ["Collected Amount Incl GST"]
)

receivable_col = find_column(
    work_orders_df,
    ["Amount Receivable"]
)

to_bill_col = find_column(
    work_orders_df,
    ["Amount To Be Billed Incl GST"]
)

amount_incl_gst_col = find_column(
    work_orders_df,
    ["Amount Incl GST"]
)


# ============================================================
# CALCULATE MAIN VALUES
# ============================================================

total_pipeline = numeric_sum(
    deals_df,
    deal_value_col
)

total_forecast = numeric_sum(
    deals_df,
    forecast_col
)

total_billed = numeric_sum(
    work_orders_df,
    billed_col
)

total_collected = numeric_sum(
    work_orders_df,
    collected_col
)

total_receivable = numeric_sum(
    work_orders_df,
    receivable_col
)

total_to_bill = numeric_sum(
    work_orders_df,
    to_bill_col
)

if total_billed != 0:

    collection_rate = (
        total_collected
        / total_billed
        * 100
    )

else:

    collection_rate = 0


# ============================================================
# AI QUERY ENGINE
# ============================================================

def answer_query(question):

    q = question.lower().strip()

    if not q:
        return "Please enter a question."


    # --------------------------------------------------------
    # TOTAL PIPELINE
    # --------------------------------------------------------

    if (
        "total pipeline" in q
        or "overall pipeline" in q
        or "pipeline total" in q
    ):

        return f"""
### 💰 Total Pipeline

**{money(total_pipeline)}**

Total Deals: **{number(len(deals_df))}**
"""


    # --------------------------------------------------------
    # FORECAST
    # --------------------------------------------------------

    if (
        "forecast value" in q
        or "total forecast" in q
        or "forecast pipeline" in q
    ):

        return f"""
### 📈 Forecast Value

**{money(total_forecast)}**
"""


    # --------------------------------------------------------
    # RECEIVABLE
    # --------------------------------------------------------

    if (
        "total receivable" in q
        or "amount receivable" in q
        or "receivable amount" in q
    ):

        return f"""
### 💳 Total Receivable

**{money(total_receivable)}**
"""


    # --------------------------------------------------------
    # BILLED
    # --------------------------------------------------------

    if (
        "total billed" in q
        or "billed value" in q
        or "billing value" in q
    ):

        return f"""
### 🧾 Total Billed

**{money(total_billed)}**
"""


    # --------------------------------------------------------
    # COLLECTED
    # --------------------------------------------------------

    if (
        "total collected" in q
        or "collected amount" in q
        or "collection amount" in q
    ):

        return f"""
### 💵 Total Collected

**{money(total_collected)}**
"""


    # --------------------------------------------------------
    # TO BE BILLED
    # --------------------------------------------------------

    if (
        "to be billed" in q
        or "amount to be billed" in q
        or "pending billing" in q
    ):

        return f"""
### 📋 Amount To Be Billed

**{money(total_to_bill)}**
"""


    # --------------------------------------------------------
    # COLLECTION RATE
    # --------------------------------------------------------

    if (
        "collection rate" in q
        or "collection percentage" in q
    ):

        return f"""
### 📊 Collection Rate

**{collection_rate:.2f}%**
"""


    # --------------------------------------------------------
    # TOTAL WORK ORDERS
    # --------------------------------------------------------

    if (
        "total work orders" in q
        or "number of work orders" in q
        or "how many work orders" in q
    ):

        return f"""
### 🔧 Total Work Orders

**{number(len(work_orders_df))}**
"""


    # --------------------------------------------------------
    # TOTAL DEALS
    # --------------------------------------------------------

    if (
        "total deals" in q
        or "number of deals" in q
        or "how many deals" in q
    ):

        return f"""
### 🤝 Total Deals

**{number(len(deals_df))}**
"""


    # --------------------------------------------------------
    # HIGHEST PIPELINE SECTOR
    # --------------------------------------------------------

    if (
        "highest pipeline" in q
        or "largest pipeline" in q
        or "top sector" in q
        or "best sector" in q
    ):

        if not deal_sector_col or not deal_value_col:

            return "Sector or Deal Value column not available."

        temp = deals_df.copy()

        temp[deal_value_col] = pd.to_numeric(
            temp[deal_value_col],
            errors="coerce"
        ).fillna(0)

        result = (
            temp.groupby(deal_sector_col)[deal_value_col]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
        )

        if result.empty:

            return "No sector data available."

        top_sector = result.iloc[0]

        return f"""
### 🏆 Highest Pipeline Sector

**{top_sector[deal_sector_col]}**

Pipeline: **{money(top_sector[deal_value_col])}**
"""


    # --------------------------------------------------------
    # SECTOR PIPELINE
    # --------------------------------------------------------

    if deal_sector_col and deal_value_col:

        sectors = (
            deals_df[deal_sector_col]
            .dropna()
            .astype(str)
            .unique()
        )

        matched_sector = None

        for sector in sectors:

            if sector.lower() in q:

                matched_sector = sector
                break

        if matched_sector:

            temp = deals_df[
                deals_df[deal_sector_col]
                .astype(str)
                .str.lower()
                == matched_sector.lower()
            ].copy()

            pipeline = numeric_sum(
                temp,
                deal_value_col
            )

            forecast = numeric_sum(
                temp,
                forecast_col
            )

            return f"""
### 📊 {matched_sector} Pipeline

**Pipeline:** {money(pipeline)}

**Forecast:** {money(forecast)}

**Deals:** {number(len(temp))}
"""


    # --------------------------------------------------------
    # WORK ORDERS BY SECTOR
    # --------------------------------------------------------

    if (
        wo_sector_col
        and (
            "work order" in q
            or "work orders" in q
        )
    ):

        sectors = (
            work_orders_df[wo_sector_col]
            .dropna()
            .astype(str)
            .unique()
        )

        for sector in sectors:

            if sector.lower() in q:

                result = work_orders_df[
                    work_orders_df[wo_sector_col]
                    .astype(str)
                    .str.lower()
                    == sector.lower()
                ]

                st.dataframe(
                    result,
                    use_container_width=True,
                    hide_index=True
                )

                return f"""
### 🔧 Work Orders — {sector}

Found **{number(len(result))}** work order(s).
"""


    # --------------------------------------------------------
    # SEARCH DEAL
    # --------------------------------------------------------

    if deal_name_col:

        deal_names = (
            deals_df[deal_name_col]
            .dropna()
            .astype(str)
            .unique()
        )

        for deal in deal_names:

            if deal.lower() in q:

                result = deals_df[
                    deals_df[deal_name_col]
                    .astype(str)
                    .str.lower()
                    == deal.lower()
                ]

                st.dataframe(
                    result,
                    use_container_width=True,
                    hide_index=True
                )

                return f"""
### 🤝 {deal}

Found **{number(len(result))}** deal record(s).
"""


    # --------------------------------------------------------
    # SHOW ALL DEALS
    # --------------------------------------------------------

    if (
        "show deals" in q
        or "all deals" in q
        or "list deals" in q
    ):

        st.dataframe(
            deals_df,
            use_container_width=True,
            hide_index=True
        )

        return f"""
### 🤝 Deals

Showing **{number(len(deals_df))}** deals.
"""


    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    return """
### ❓ I couldn't understand that question.

Try:

- What is the total pipeline?
- What is the forecast value?
- Which sector has the highest pipeline?
- What is the Mining pipeline?
- What is the Renewables pipeline?
- Show Amazon deal
- Show Apple deal
- Show work orders for Mining
- What is the total receivable?
- What is the total billed value?
- What is the total collected amount?
- What is the amount to be billed?
- What is the collection rate?
"""


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("📊 Skylark BI")

st.sidebar.caption(
    "Monday.com Business Intelligence"
)

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Deals",
        "Work Orders",
        "Pipeline by Sector",
        "AI Query"
    ]
)

st.sidebar.divider()

st.sidebar.write(
    f"Deals: **{len(deals_df)}**"
)

st.sidebar.write(
    f"Work Orders: **{len(work_orders_df)}**"
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">📊 Skylark BI Agent</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    'Monday.com Business Intelligence Dashboard'
    '</div>',
    unsafe_allow_html=True
)

st.divider()


# ============================================================
# DASHBOARD
# ============================================================

if page == "Dashboard":

    st.header("📊 Overall Business Summary")

    # Sales
    st.subheader("Sales Pipeline")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Total Deals",
        number(len(deals_df))
    )

    c2.metric(
        "Total Pipeline",
        money(total_pipeline)
    )

    c3.metric(
        "Forecast Value",
        money(total_forecast)
    )

    st.divider()

    # Billing
    st.subheader("💰 Work Order & Billing")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Work Orders",
        number(len(work_orders_df))
    )

    c2.metric(
        "Billed",
        money(total_billed)
    )

    c3.metric(
        "Collected",
        money(total_collected)
    )

    c4.metric(
        "Receivable",
        money(total_receivable)
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "To Be Billed",
        money(total_to_bill)
    )

    c2.metric(
        "Collection Rate",
        f"{collection_rate:.2f}%"
    )

    c3.metric(
        "Data Records",
        number(
            len(deals_df)
            + len(work_orders_df)
        )
    )


# ============================================================
# DEALS
# ============================================================

elif page == "Deals":

    st.header("🤝 Deals")

    search = st.text_input(
        "🔎 Search Deals",
        placeholder="Enter deal name, sector, customer..."
    )

    result = search_dataframe(
        deals_df,
        search
    )

    st.write(
        f"Showing **{len(result)}** "
        f"of **{len(deals_df)}** deals"
    )

    st.dataframe(
        result,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# WORK ORDERS
# ============================================================

elif page == "Work Orders":

    st.header("🔧 Work Orders")

    search = st.text_input(
        "🔎 Search Work Orders",
        placeholder="Enter deal, customer, sector..."
    )

    result = search_dataframe(
        work_orders_df,
        search
    )

    st.write(
        f"Showing **{len(result)}** "
        f"of **{len(work_orders_df)}** work orders"
    )

    st.dataframe(
        result,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# PIPELINE BY SECTOR
# ============================================================

elif page == "Pipeline by Sector":

    st.header("📈 Pipeline by Sector")

    if not deal_sector_col or not deal_value_col:

        st.error(
            "Sector or Deal Value column not found."
        )

    else:

        temp = deals_df.copy()

        temp[deal_value_col] = pd.to_numeric(
            temp[deal_value_col],
            errors="coerce"
        ).fillna(0)

        if forecast_col:

            temp[forecast_col] = pd.to_numeric(
                temp[forecast_col],
                errors="coerce"
            ).fillna(0)

        else:

            temp["Forecast"] = 0
            forecast_col = "Forecast"

        sector_summary = (
            temp.groupby(deal_sector_col)
            .agg(
                Deals=(deal_value_col, "count"),
                Pipeline=(deal_value_col, "sum"),
                Forecast=(forecast_col, "sum")
            )
            .reset_index()
            .sort_values(
                "Pipeline",
                ascending=False
            )
        )

        st.dataframe(
            sector_summary,
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Pipeline Chart")

        chart_data = (
            sector_summary
            .set_index(deal_sector_col)
            [["Pipeline", "Forecast"]]
        )

        st.bar_chart(chart_data)


# ============================================================
# AI QUERY
# ============================================================

elif page == "AI Query":

    st.header("🤖 AI Natural Language BI")

    st.write(
        "Ask questions about your Monday.com business data."
    )

    st.info(
        "Ask questions such as: "
        "'What is the total pipeline?'"
    )

    question = st.text_input(
        "💬 Ask your question",
        placeholder="Example: What is the Mining pipeline?"
    )

    if question:

        st.divider()

        st.markdown(
            f"**Your question:** {question}"
        )

        try:

            answer = answer_query(question)

            st.markdown(answer)

        except Exception as e:

            st.error(
                "Error processing your question."
            )

            st.exception(e)

    st.divider()

    st.subheader("Example Questions")

    examples = [
        "What is the total pipeline?",
        "What is the forecast value?",
        "Which sector has the highest pipeline?",
        "What is the Mining pipeline?",
        "What is the Renewables pipeline?",
        "Show Amazon deal",
        "Show Apple deal",
        "Show work orders for Mining",
        "What is the total receivable?",
        "What is the total billed value?",
        "What is the total collected amount?",
        "What is the amount to be billed?",
        "What is the collection rate?"
    ]

    for example in examples:

        st.write(
            "• " + example
        )