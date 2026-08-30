import os
from dotenv import load_dotenv
from google import genai

from bi_engine import load_bi_data


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found. "
        "Add it to your .env file."
    )

client = genai.Client(api_key=GEMINI_API_KEY)


# ============================================================
# LOAD BI DATA
# ============================================================

print()
print("=" * 46)
print("          SKYLARK AI BI AGENT")
print("=" * 46)

print()
print("Loading BI data...")

bi_data = load_bi_data()


# ============================================================
# HANDLE CURRENT bi_engine RETURN FORMAT
# ============================================================

# Your current bi_engine.py returns:
#
#     (deals, work_orders)
#
# Therefore unpack the tuple.

if isinstance(bi_data, tuple):
    deals, work_orders = bi_data

elif isinstance(bi_data, dict):
    deals = bi_data.get("deals", [])
    work_orders = bi_data.get("work_orders", [])

else:
    raise TypeError(
        "Unexpected return type from load_bi_data(): "
        + str(type(bi_data))
    )


print()
print("BI data loaded successfully.")
print(f"Deals: {len(deals)}")
print(f"Work Orders: {len(work_orders)}")


# ============================================================
# CREATE DATA SUMMARY FOR GEMINI
# ============================================================

def create_data_summary(deals, work_orders):

    summary = {
        "deals": deals,
        "work_orders": work_orders
    }

    return summary


data = create_data_summary(deals, work_orders)


# ============================================================
# GEMINI QUERY FUNCTION
# ============================================================

def ask_gemini(question):

    prompt = f"""
You are Skylark BI Agent.

You answer questions about business intelligence data.

You have two datasets:

1. Deals
2. Work Orders

IMPORTANT:
- Use ONLY the supplied data.
- Do not invent numbers.
- If the requested information is unavailable, say so.
- Give calculations clearly.
- Use Indian Rupee formatting when discussing money.
- Keep answers concise and business-friendly.

DEALS DATA:
{deals}

WORK ORDERS DATA:
{work_orders}

USER QUESTION:
{question}

Answer the user's question using the data above.
"""

    try:

        response = client.models.generate_content(
            model="gemini-3.7-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:

        return f"Gemini API error: {e}"


# ============================================================
# MAIN CHAT LOOP
# ============================================================

print()
print("=" * 46)
print("       SKYLARK NATURAL LANGUAGE BI")
print("=" * 46)

print()
print("Ask questions about your business data.")
print()
print("Examples:")
print("  What is the total pipeline?")
print("  Which sector has the highest pipeline?")
print("  Show Amazon deals")
print("  Show Apple deal")
print("  What is the Mining pipeline?")
print("  Show Renewables deals")
print("  What is the total receivable?")
print("  Show work orders for Mining")
print()
print("Type 'exit' to quit.")
print()


while True:

    try:
        question = input("You: ").strip()

    except KeyboardInterrupt:
        print()
        break

    if not question:
        continue

    if question.lower() in ["exit", "quit", "bye"]:
        print()
        print("Thank you for using Skylark BI Agent.")
        break

    print()
    print("Thinking...")

    answer = ask_gemini(question)

    print()
    print("Skylark BI Agent:")
    print(answer)
    print()