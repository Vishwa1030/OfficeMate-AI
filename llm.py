import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def get_client():

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        return None

    return OpenAI(
        api_key=api_key
    )


def generate_answer(context, question):

    client = get_client()

    if client is None:

        return (
            "The LLM connection is not configured. "
            "Please add OPENAI_API_KEY to the .env file."
        )

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-5.6-luna"
    )

    instructions = """
You are OfficeMate AI.

You are an enterprise workplace assistant.

Use only the supplied workplace policy and
live database context.

Do not invent:
- employees
- schedules
- parking slots
- attendance
- tasks
- cafeteria availability
- company policies

If the required information is not available,
say that the current system does not contain
that information.

Do not claim access to private company systems
unless the supplied context confirms it.

Keep answers clear and concise.
"""

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=f"""
{context}

QUESTION:
{question}
"""
    )

    return response.output_text