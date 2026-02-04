from services.supabase_client import supabase
from services.embeddings import create_embedding

def store_user(email):
    existing = supabase.table("users") \
        .select("id") \
        .eq("email", email) \
        .execute()

    if existing.data:
        return existing.data[0]["id"]

    res = supabase.table("users").insert({
        "email": email
    }).execute()

    return res.data[0]["id"]

def store_document(user_id, filename):
    res = supabase.table("documents").insert({
        "user_id": user_id,
        "filename": filename
    }).execute()

    return res.data[0]["id"]

def store_chunk(document_id, chunk_text):
    embedding = create_embedding(chunk_text)

    supabase.table("chunks").insert({
        "document_id": document_id,
        "chunk_text": chunk_text,
        "embedding": embedding
    }).execute()
