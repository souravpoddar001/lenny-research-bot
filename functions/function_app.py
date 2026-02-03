"""
Azure Functions HTTP endpoints for Lenny's Research Bot.

Endpoints:
- POST /api/query - Quick Q&A (sync, <10s)
- POST /api/research - Deep research (async, 30-60s)
- GET /api/health - Health check
- GET /api/history - Get query history for current session
- GET /api/popular - Get popular queries by access count
- GET /api/cached - Get cached result by cache key

Retrieval Mode:
- "pageindex" (default): LLM reasoning-based retrieval through hierarchical index
- "vector" (optional): Traditional Azure AI Search with embeddings (requires additional config)
"""

import os
import json
import logging
import traceback
import azure.functions as func
from azure.durable_functions import DFApp

from shared.research import DeepResearchPipeline
from shared.search import SearchClient
from shared.history import get_session_history, add_to_history
from shared.cache import get_popular_queries, get_by_cache_key

# Initialize the function app with durable functions
app = DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Initialize shared clients (lazy loaded per mode)
_pipelines = {}
_search_client = None

# Default retrieval mode: pageindex (LLM reasoning) or vector (Azure AI Search)
DEFAULT_RETRIEVAL_MODE = os.environ.get("RETRIEVAL_MODE", "pageindex")
logging.info(f"DEFAULT_RETRIEVAL_MODE: {DEFAULT_RETRIEVAL_MODE}")


def get_pipeline(mode: str = None) -> DeepResearchPipeline:
    """
    Lazy load the research pipeline for the specified mode.

    Args:
        mode: "vector" or "pageindex" (defaults to DEFAULT_RETRIEVAL_MODE)

    Returns:
        DeepResearchPipeline configured for the specified mode
    """
    global _pipelines
    logging.info(f"get_pipeline called with mode={mode}, DEFAULT_RETRIEVAL_MODE={DEFAULT_RETRIEVAL_MODE}")
    mode = mode or DEFAULT_RETRIEVAL_MODE
    logging.info(f"Using mode: {mode}")

    if mode not in _pipelines:
        logging.info(f"Initializing pipeline with retrieval_mode={mode}")
        _pipelines[mode] = DeepResearchPipeline(retrieval_mode=mode)

    return _pipelines[mode]


def get_search_client() -> SearchClient:
    """Lazy load the search client."""
    global _search_client
    if _search_client is None:
        _search_client = SearchClient()
    return _search_client


@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    return func.HttpResponse(
        json.dumps({"status": "healthy", "service": "lenny-research-bot"}),
        mimetype="application/json",
    )


@app.route(route="history", methods=["GET"])
def get_history(req: func.HttpRequest) -> func.HttpResponse:
    """Get query history for the current session."""
    session_id = req.headers.get("X-Session-ID", "")

    if not session_id:
        return func.HttpResponse(
            json.dumps({"queries": []}),
            mimetype="application/json",
        )

    queries = get_session_history(session_id)

    return func.HttpResponse(
        json.dumps({"queries": queries}),
        mimetype="application/json",
    )


@app.route(route="popular", methods=["GET"])
def get_popular(req: func.HttpRequest) -> func.HttpResponse:
    """Get popular queries by access count."""
    try:
        limit = min(int(req.params.get("limit", "10")), 50)
    except ValueError:
        limit = 10

    queries = get_popular_queries(limit)

    return func.HttpResponse(
        json.dumps({"queries": queries}),
        mimetype="application/json",
    )


@app.route(route="cached", methods=["GET"])
def get_cached(req: func.HttpRequest) -> func.HttpResponse:
    """Get a cached result by cache key (for sidebar click)."""
    cache_key = req.params.get("key", "")

    if not cache_key:
        return func.HttpResponse(
            json.dumps({"error": "Missing 'key' parameter"}),
            status_code=400,
            mimetype="application/json",
        )

    result = get_by_cache_key(cache_key)

    if result is None:
        return func.HttpResponse(
            json.dumps({"error": "Cache entry not found"}),
            status_code=404,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps(result),
        mimetype="application/json",
    )


@app.route(route="query", methods=["POST"])
def quick_query(req: func.HttpRequest) -> func.HttpResponse:
    """
    Quick Q&A endpoint for simple questions.

    Request body:
    {
        "query": "What is product-market fit?",
        "mode": "pageindex"  // optional: "vector" (default) or "pageindex"
    }

    Response:
    {
        "content": "...",
        "citations": [...],
        "sources": [...]
    }
    """
    try:
        body = req.get_json()
        query = body.get("query")
        mode = body.get("mode")  # Optional: "vector" or "pageindex"

        if not query:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'query' in request body"}),
                status_code=400,
                mimetype="application/json",
            )

        pipeline = get_pipeline(mode=mode)
        result = pipeline.quick_query(query)

        return func.HttpResponse(
            json.dumps(result.to_dict()),
            mimetype="application/json",
        )

    except Exception as e:
        logging.error(f"Error in quick_query: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )


@app.route(route="research", methods=["POST"])
def deep_research(req: func.HttpRequest) -> func.HttpResponse:
    """
    Deep research endpoint for comprehensive analysis.

    Request body:
    {
        "query": "How do top PMs think about product-market fit?",
        "output_type": "article",  // optional: article, report, qa_response
        "mode": "pageindex"  // optional: "vector" (default) or "pageindex"
    }

    Response:
    {
        "content": "...",
        "citations": [...],
        "sources": [...],
        "unverified_quotes": [...]
    }
    """
    try:
        body = req.get_json()
        query = body.get("query")
        mode = body.get("mode")  # Optional: "vector" or "pageindex"
        session_id = req.headers.get("X-Session-ID", "")

        if not query:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'query' in request body"}),
                status_code=400,
                mimetype="application/json",
            )

        pipeline = get_pipeline(mode=mode)
        result = pipeline.research(query)

        # Add to session history if session ID provided
        if session_id:
            add_to_history(session_id, query)

        return func.HttpResponse(
            json.dumps(result.to_dict()),
            mimetype="application/json",
        )

    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f"Error in deep_research: {e}\n{tb}")
        return func.HttpResponse(
            json.dumps({"error": str(e), "traceback": tb}),
            status_code=500,
            mimetype="application/json",
        )


@app.route(route="search", methods=["POST"])
def search_transcripts(req: func.HttpRequest) -> func.HttpResponse:
    """
    Direct search endpoint for debugging and exploration.

    Request body:
    {
        "query": "product-market fit",
        "top_k": 10,
        "chunk_type": "speaker_turn",  // optional
        "guest": "Rahul Vohra"  // optional
    }
    """
    try:
        body = req.get_json()
        query = body.get("query")
        top_k = body.get("top_k", 10)
        chunk_type = body.get("chunk_type")
        guest = body.get("guest")

        if not query:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'query' in request body"}),
                status_code=400,
                mimetype="application/json",
            )

        search_client = get_search_client()
        results = search_client.hybrid_search(
            query=query,
            top_k=top_k,
            chunk_type=chunk_type,
            guest=guest,
        )

        # Remove vectors from response (too large)
        for r in results:
            r.pop("content_vector", None)

        return func.HttpResponse(
            json.dumps({"results": results, "count": len(results)}),
            mimetype="application/json",
        )

    except Exception as e:
        logging.error(f"Error in search: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )
