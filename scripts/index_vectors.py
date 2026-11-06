"""Index permitted local precedents into local Qdrant. Never indexes test labels."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.policy_engine import assess
from app.repositories import get_approval, list_cases
from app.schemas import Opportunity


def precedent_rows() -> list[dict]:
    """Only human-approved cases are indexable; source-stage Won is not a repo."""
    rows = []
    for row in list_cases():
        case = row["case"]
        approval = get_approval(case["opportunity_id"])
        approved = (row["review_status"] == "approved" and row["evaluation"] and
                    not row["evaluation"].get("blockers") and approval is not None and
                    approval["decision"] == "approve" and approval["case_version"] == row["case_version"] and
                    not assess(Opportunity.model_validate(case), evidence_max_age_days=settings.evidence_max_age_days)["blockers"])
        if approved:
            rows.append({"case": case, "case_version": row["case_version"],
                         "precedent_type": "human_approved"})
    return rows


def main() -> int:
    if urlsplit(settings.qdrant_url).hostname not in {"127.0.0.1", "localhost"}:
        print("QDRANT_URL must point to localhost for this POC", file=sys.stderr)
        return 2
    try:
        from qdrant_client import QdrantClient, models
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("Install optional packages: python -m pip install -r requirements-vectors.txt", file=sys.stderr)
        return 2
    rows = precedent_rows()
    if not rows:
        print("No permitted precedents to index. Nothing changed.")
        return 0
    model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    try:
        # Cache-only load prevents accidental transfer of internal case text.
        encoder = SentenceTransformer(model_name, local_files_only=True)
        client = QdrantClient(url=settings.qdrant_url, timeout=5)
        client.get_collections()
        collection = os.getenv("QDRANT_COLLECTION", "forge_precedents")
        size = encoder.get_sentence_embedding_dimension()
        if size is None:
            raise RuntimeError("Embedding dimension is unknown")
        if not client.collection_exists(collection):
            client.create_collection(collection_name=collection,
                                     vectors_config=models.VectorParams(size=size, distance=models.Distance.COSINE))
        points = []
        for row in rows:
            case = row["case"]
            text = " | ".join(str(x or "") for x in
                              (case.get("practice"), case.get("opportunity_name"), case.get("level30_description"),
                               case.get("optimization_type")))
            vector = encoder.encode(text, normalize_embeddings=True).tolist()
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"forge:{case['opportunity_id']}:{row['case_version']}"))
            payload = {"source_id": case["opportunity_id"], "practice": case["practice"],
                       "case_version": row["case_version"], "precedent_type": row["precedent_type"],
                       "source_system": case.get("source_system"), "synthetic": bool(case.get("synthetic"))}
            points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))
        client.upsert(collection_name=collection, points=points, wait=True)
    except Exception as exc:
        print(f"Vector indexing unavailable: {exc}", file=sys.stderr)
        return 1
    print(f"Indexed {len(points)} permitted precedents into local Qdrant collection {collection}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
