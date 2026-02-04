from services.llm import call_llm

def answer_question(context, question):
    prompt = f"""
You are an expert document analyst.

Use ONLY the document content below.

If the question asks for lists or multiple values,
return results in clean bullet points or tables.

Document:
{context}

Question:
{question}

Answer clearly.
"""

    return call_llm(prompt)
