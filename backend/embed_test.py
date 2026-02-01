from app.llm import get_embedder

emb = get_embedder()

print(emb.embed("Helllooooo"))
