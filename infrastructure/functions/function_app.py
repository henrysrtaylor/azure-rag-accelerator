"""
Azure Function: Get Security Groups for Document

This function is called by Azure AI Search indexer as a custom skill.
It looks up security groups for a document from a JSON file (local testing)
or Cosmos DB (production).

Input:  document_name (e.g., "document.pdf")
Output: ["group-a", "group-b"] (array for index)

Deploy to Azure Functions, then add the skill to your indexer.
"""

import azure.functions as func
import json
import logging
from pathlib import Path

app = func.FunctionApp()

# Load document security groups from JSON file (for local testing)
# In production, replace with Cosmos DB lookup
_SECURITY_GROUPS_FILE = Path(__file__).parent / "document_security_groups.json"

def _load_document_groups() -> dict:
    """Load document -> groups mapping from JSON file."""
    if _SECURITY_GROUPS_FILE.exists():
        with open(_SECURITY_GROUPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Cache at module level - loaded once at startup
_DOCUMENT_GROUPS = _load_document_groups()


@app.route(route="health", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint with environment variable verification.

    Args:
        req: HTTP request object.

    Returns:
        JSON response with health status.
    """
    logging.info('Health check request received.')

    health_status = {
        "fromPipeline": True,
        "status": "healthy",
        "health_endpoint_response": True,
        "security_file_loaded": _SECURITY_GROUPS_FILE.exists()
    }

    status_code = 200 if health_status["status"] == "healthy" else 503

    return func.HttpResponse(
        json.dumps(health_status, indent=2),
        mimetype="application/json",
        status_code=status_code
    )


@app.route(route="get_security_groups", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def get_security_groups(req: func.HttpRequest) -> func.HttpResponse:
    """
    Custom skill endpoint for Azure AI Search indexer.

    Looks up security groups for a document by name from a JSON mapping file.

    Args:
        req: HTTP request with Azure Search custom skill format.

    Returns:
        JSON response with security_groups array for each document.
    """
    logging.info("Get security groups skill invoked")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}),
            status_code=400,
            mimetype="application/json"
        )

    values = body.get("values", [])
    results = []

    for record in values:
        record_id = record.get("recordId", None)
        data = record.get("data", {})
        document_name = data.get("document_name", "")

        security_groups = _DOCUMENT_GROUPS.get(document_name, [])

        if not security_groups:
            logging.warning(f"No security groups found for document: {document_name}")

        results.append({
            "recordId": record_id,
            "data": {
                "security_groups": security_groups
            }
        })

    return func.HttpResponse(
        json.dumps({"values": results}),
        status_code=200,
        mimetype="application/json"
    )
