"""FastAPI backend server for RAG chat API.

Provides REST endpoints for chat and health checks.
Run with: uvicorn app.backend_server:app --reload
"""
import os
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from raglib.config import load_env_vars
from raglib.permissions import build_security_filter
from raglib.pipeline import failure_chat_response, inference_chat_logic

load_env_vars()

app = FastAPI(
    title="RAG Chat API",
    description="API for RAG-based chat interactions with guardrails and query refinement",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    """Chat message with role and content."""
    role: str = Field(..., description="Role of the message sender (user/assistant)")
    content: str = Field(..., description="Content of the message")


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    chat_history: list[Message] = Field(..., description="List of previous chat messages")
    security_groups: Optional[list[str]] = Field(default=None, description="User security groups for DLS filtering")
    enable_query_refinement: bool = Field(..., description="Refine the latest user query before retrieval")
    enable_guardrail_checks: bool = Field(..., description="Validate the latest user message before retrieval")
    enable_suggested_questions: bool = Field(..., description="Generate follow-up questions")


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""
    assistant_message: Message = Field(..., description="The assistant's response message")
    suggested_questions: list = Field(default=[], description="List of suggested follow-up questions")
    references: list = Field(default=[], description="List of citation references")
    guardrail_triggered: bool = Field(default=False, description="Whether a guardrail handled the request")
    guardrail_type: Optional[str] = Field(default=None, description="Type of triggered guardrail")
    save_chat_history: bool = Field(default=True, description="Whether clients should persist this turn")
    end_conversation: bool = Field(default=False, description="Whether an interactive client should end the conversation")


@app.get("/", tags=["Health"])
def root() -> dict:
    """Root endpoint - API welcome message."""
    return {"message": "RAG Chat API", "status": "running", "version": "1.0.0"}


@app.get("/health_check", tags=["Health"])
def health_check() -> dict:
    """Health check with environment variable verification."""
    try:
        # Check if environment variables are loaded
        required_vars = [
            "PARAMETER_CHUNK_SIZE",
            "PARAMETER_CHUNK_OVERLAP",
            "PARAMETER_NUMBER_DOC_RETRIEVE",
            "PARAMETER_K_NEAREST_NEIGHBORS",
            "PARAMETER_SUGGESTED_QUESTIONS",
            "PARAMETER_HATE_GUARDRAIL_THRESHOLD",
            "PARAMETER_SELFHARM_GUARDRAIL_THRESHOLD",
            "PARAMETER_SEXUAL_GUARDRAIL_THRESHOLD",
            "PARAMETER_VIOLENCE_GUARDRAIL_THRESHOLD",
            "AZURE_FOUNDRY_LARGE_DEPLOYED_MODEL",
            "AZURE_FOUNDRY_SMALL_DEPLOYED_MODEL",
            "AZURE_FOUNDRY_EMBEDDING_DEPLOYED_MODEL",
            "AZURE_FOUNDRY_EMBEDDING_DIMENSIONS",
            "AZURE_FOUNDRY_LARGE_DEPLOYED_MODEL_VERSION",
            "AZURE_FOUNDRY_SMALL_DEPLOYED_MODEL_VERSION",
            "AZURE_FOUNDRY_EMBEDDING_DEPLOYED_MODEL_VERSION",
            "AZURE_SUBSCRIPTION_ID",
            "AZURE_RESOURCE_GROUP",
            "AZURE_FOUNDRY_RESOURCE",
            "AZURE_FOUNDRY_ENDPOINT",
            "AZURE_FOUNDRY_API_VERSION",
            "AZURE_CONTENT_MODERATOR_ENDPOINT",
            "AZURE_CONTENT_MODERATOR_API_VERSION",
            "COGNITIVE_SERVICES_ENDPOINT",
            "AZURE_SEARCH_SERVICE_ENDPOINT",
            "AZURE_SEARCH_API_VERSION",
            "AZURE_SEARCH_PROJECT_PREFIX",
            "STORAGE_ACCOUNT_NAME",
            "DOCUMENTS_FILESYSTEM_NAME",
            "EVALUATION_FILESYSTEM_NAME",
            "EVALUATION_DOCUMENT_NAME",
            "STORAGE_DFS_ACCOUNT_URL",
            "STORAGE_CONNECTION_STRING",
            "LOGGING_CONNECTION_STRING"
        ]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            return {
                "status": "unhealthy",
                "message": f"Missing environment variables: {', '.join(missing_vars)}",
                "missing_count": len(missing_vars),
                "total_required": len(required_vars)
            }
        
        return {
            "status": "healthy",
            "environment": "configured",
            "variables_loaded": len(required_vars)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a chat request and return RAG-generated response."""
    try:
        # Convert Pydantic models to dict for the function
        chat_history_dict = [dict(msg) for msg in request.chat_history]
        
        # Build security filter from groups passed by application
        security_filter = build_security_filter(request.security_groups)
        
        # Call the inference logic
        response = inference_chat_logic(
            chat_history=chat_history_dict,
            security_filter=security_filter,
            enable_query_refinement=request.enable_query_refinement,
            enable_guardrail_checks=request.enable_guardrail_checks,
            enable_suggested_questions=request.enable_suggested_questions,
        )
        
        return response
    except Exception:
        return failure_chat_response()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)