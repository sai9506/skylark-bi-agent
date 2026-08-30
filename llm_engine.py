import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def get_client():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set in the .env file."
        )

    return OpenAI(api_key=api_key)


def ask_llm(question, context):
    """
    Send a business question and BI data context
    to the OpenAI model.
    """

    client = get_client()

    prompt = f"""
You are Skylark BI Agent, a business intelligence assistant.

Answer the user's question using ONLY the business
data provided below.

BUSINESS DATA:
{context}

USER QUESTION:
{question}

Rules:
1. Use the provided data.
2. Do not invent numbers.
3. Show calculations when useful.
4. Give a concise business-friendly answer.
5. Use Indian Rupee formatting when discussing money.
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    return response.output_text