"""Command-line chat client for the RAG API.

Provides an interactive terminal interface with MSAL authentication
for document-level security. Calls the backend API endpoints.
"""
import os

import msal
import requests

from raglib.config import load_env_vars

load_env_vars()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

OPTION_QUERY_REFINEMENT = True
OPTION_GUARDRAIL_CHECKS = True
OPTION_SUGGESTED_QUESTIONS = True
OPTION_SECURITY_GROUPS = True
STATIC_RESPONSES = {
    "entry": "Hello! I'm your RAG assistant. How can I help you today?",
}


def authenticate_user() -> list[str]:
    """
    Authenticate user via MSAL and extract security groups.

    Opens browser for interactive Microsoft login.

    Returns:
        List of security group GUIDs from the user's token.
    """
    client_id = os.getenv("AZURE_CLIENT_ID")
    tenant_id = os.getenv("AZURE_TENANT_ID")
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    
    # Create public client app (no client secret needed for user auth)
    app = msal.PublicClientApplication(
        client_id,
        authority=authority
    )
    
    # Scopes - User.Read gets us basic profile + groups
    scopes = ["User.Read"]
    
    # Try to get cached token first
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(scopes, account=accounts[0])
    
    # No cached token - interactive login
    if not result:
        print("\n[Opening browser for Microsoft login...]")
        result = app.acquire_token_interactive(scopes=scopes)
    
    if "error" in result:
        raise Exception(f"Authentication failed: {result.get('error_description', result.get('error'))}")
    
    # Extract groups from ID token claims
    id_token_claims = result.get("id_token_claims", {})
    groups = id_token_claims.get("groups", [])
    
    user_name = id_token_claims.get("name", "Unknown")
    print(f"\n[Authenticated as: {user_name}]")
    print(f"[Security groups: {len(groups)} group(s)]")
    
    if not groups:
        print("[WARNING: No groups found in token. Check App Registration token configuration.]")
        return []
    
    return groups


def interactive_chat() -> None:
    """Run interactive chat loop in terminal."""
    # Handle security groups based on option
    if OPTION_SECURITY_GROUPS:
        security_groups = authenticate_user()
    else: # [] means no groups, which will deny all access in DLS filter logic. None means bypass DLS filter (full access).
        security_groups = None

    chat_history: list[dict[str, str]] = []

    print("\nRAG Assistant\n")
    while True:
        # Entry message
        if len(chat_history) == 0:
            print(f"\nAssistant: {STATIC_RESPONSES['entry']}")

        user_query = input("\nUser: ")

        # Chat logic
        try:
            response = requests.post(f"{API_BASE_URL}/chat", json={
                "chat_history": chat_history + [{"role": "user", "content": user_query}],
                "security_groups": security_groups,
                "enable_query_refinement": OPTION_QUERY_REFINEMENT,
                "enable_guardrail_checks": OPTION_GUARDRAIL_CHECKS,
                "enable_suggested_questions": OPTION_SUGGESTED_QUESTIONS,
            })
            response.raise_for_status()
            chat_response = response.json()
        except requests.RequestException as e:
            print(f"\n[Error calling chat API: {e}]")
            continue
                
        model_answer = chat_response.get("assistant_message", {}).get("content", "")
        suggested_questions = chat_response.get("suggested_questions", [])
        references = chat_response.get("references", [])
        
        print(f"\nAssistant: {model_answer}")
        if len(references) > 0:
            print("\nReferences:")
            for ref in references:
                ref_id = ref['id']
                ref_text = ref['text']
                print(f"- [{ref_id}]. {ref_text}")
        if len(suggested_questions) > 0:
            print("\nSuggested Questions:")
            for sug in suggested_questions:
                sug_text = sug['text']
                print(f"- {sug_text}")

        if chat_response.get("save_chat_history", True):
            chat_history.extend([
                {"role": "user", "content": user_query},
                chat_response["assistant_message"],
            ])
            chat_history = chat_history[-12:]

        if chat_response.get("end_conversation", False):
            break


if __name__ == "__main__":
    interactive_chat()
