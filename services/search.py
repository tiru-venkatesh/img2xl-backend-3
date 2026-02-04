from services.supabase_client import supabase
from services.embeddings import create_embedding

def search_chunks(query, top_k=5):
    query_vec = create_embedding(query)

    res = supabase.rpc(
        "match_chunks",
        {
            "query_embedding": query_vec,
            "match_count": top_k
        }
    ).execute()

    return res.data
