# Future Azure migration notes — planning only

The current FORGE POC is local and uses FastAPI, Streamlit, SQLite, JSON, LangGraph, and optional Qdrant in Podman. Nothing in this document authorizes or performs a deployment.

1. Package the API/UI as OCI-compatible containers after local tests pass. Azure Container Apps is a possible hosting option, subject to organizational approval.
2. Replace local raw/reference JSON with controlled object storage, such as Azure Blob Storage, after classifying the workbook and derived data. Preserve source IDs and provenance.
3. Select a production-appropriate transactional and checkpoint store after requirements review. SQLite is a local POC choice; no PostgreSQL decision is implied.
4. Move secrets to Key Vault and reviewer identity/roles to company SSO. Remove shared local tokens before any multi-user deployment.
5. Decide whether Qdrant remains self-hosted or a managed vector service is approved. Reindex permitted precedents only; similarity remains a review candidate.
6. Add private networking, access controls, audit retention, monitoring, backup, and data residency review before handling real customer data.
7. Azure AI Foundry or another model service is optional and would require separate credit, data, and security approval. Deterministic policy gates and human approval remain authoritative.

The FastAPI result contract, hard-gate reason codes, and human approval semantics should remain stable through migration. No Azure account, paid service, or production integration is required for the local hackathon POC.
