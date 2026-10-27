"""Create the Atlas Vector Search index on chunks.embedding.

Run once (after choosing the embedding model): python -m app.db.vector_index
The filter fields let every search be restricted to one user / project / file / topic.
"""
import time

from pymongo.operations import SearchIndexModel

from app.core.config import get_settings
from app.db.mongo import get_sync_db

INDEX_NAME = "chunks_vector"


def definition(dim: int) -> dict:
    return {
        "fields": [
            {"type": "vector", "path": "embedding", "numDimensions": dim, "similarity": "cosine"},
            {"type": "filter", "path": "user_id"},
            {"type": "filter", "path": "project_id"},
            {"type": "filter", "path": "artifact_id"},
            {"type": "filter", "path": "topic"},
            {"type": "filter", "path": "kind"},
            {"type": "filter", "path": "is_active"},
        ]
    }


def main() -> None:
    db = get_sync_db()
    if "chunks" not in db.list_collection_names():
        db.create_collection("chunks")
    existing = {ix["name"]: ix for ix in db.chunks.list_search_indexes()}
    model_def = definition(get_settings().embedding_dim)
    if INDEX_NAME in existing:
        db.chunks.update_search_index(INDEX_NAME, model_def)
        print(f"Updated {INDEX_NAME}")
    else:
        db.chunks.create_search_index(SearchIndexModel(definition=model_def, name=INDEX_NAME, type="vectorSearch"))
        print(f"Created {INDEX_NAME}")

    for _ in range(60):
        status = next((ix for ix in db.chunks.list_search_indexes(INDEX_NAME)), {})
        if status.get("queryable"):
            print("Index is ready")
            return
        time.sleep(5)
    print("Index is still building; it becomes usable in a minute or two")


if __name__ == "__main__":
    main()
