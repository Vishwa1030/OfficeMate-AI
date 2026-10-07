from rag import retrieve_context
from llm import generate_answer


def ask_officemate(user_id, question):

    if user_id is None:

        return (
            "Please log in before using "
            "the OfficeMate AI assistant."
        )

    if not question or not question.strip():

        return (
            "Please enter a question."
        )

    context = retrieve_context(
        user_id,
        question
    )

    return generate_answer(
        context,
        question
    )