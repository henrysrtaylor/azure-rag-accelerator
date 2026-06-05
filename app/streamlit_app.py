"""Streamlit chat interface for the RAG API.

Run with: streamlit run app/streamlit_app.py
"""
import os

import msal
import requests
import streamlit as st

from raglib.config import load_env_vars

load_env_vars()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Default values from env vars (can be overridden by toggles)
DEFAULT_GUARDRAIL_CHECKS = os.getenv("OPTION_GUARDRAIL_CHECKS", "true").lower() in ("true", "1", "yes")
DEFAULT_SECURITY_GROUPS = os.getenv("OPTION_SECURITY_GROUPS", "true").lower() in ("true", "1", "yes")
DEFAULT_SHOW_REFERENCES = True
DEFAULT_SHOW_SUGGESTED_QS = True


def authenticate_user() -> list[str]:
    """Authenticate user via MSAL and extract security groups."""
    client_id = os.getenv("AZURE_CLIENT_ID")
    tenant_id = os.getenv("AZURE_TENANT_ID")
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    
    app = msal.PublicClientApplication(client_id, authority=authority)
    scopes = ["User.Read"]
    
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(scopes, account=accounts[0])
    
    if not result:
        result = app.acquire_token_interactive(scopes=scopes)
    
    if "error" in result:
        raise Exception(f"Authentication failed: {result.get('error_description', result.get('error'))}")
    
    id_token_claims = result.get("id_token_claims", {})
    groups = id_token_claims.get("groups", [])
    user_name = id_token_claims.get("name", "Unknown")
    
    return groups, user_name


# Page config - hide deploy button via CSS
st.set_page_config(
    page_title="RAG Assistant", 
    page_icon="💬", 
    layout="centered"
)

# Hide deploy button with CSS + right-align user messages
st.markdown("""
    <style>
    .stDeployButton {display: none !important;}
    [data-testid="stAppDeployButton"] {display: none !important;}
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stMarkdownContainer"] {
        text-align: right;
    }
    </style>
""", unsafe_allow_html=True)

st.title("💬 RAG Assistant")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "security_groups" not in st.session_state:
    st.session_state.security_groups = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None
# Option toggles - initialized from defaults
if "opt_auth" not in st.session_state:
    st.session_state.opt_auth = DEFAULT_SECURITY_GROUPS
if "opt_guardrails" not in st.session_state:
    st.session_state.opt_guardrails = DEFAULT_GUARDRAIL_CHECKS
if "opt_references" not in st.session_state:
    st.session_state.opt_references = DEFAULT_SHOW_REFERENCES
if "opt_suggested_qs" not in st.session_state:
    st.session_state.opt_suggested_qs = DEFAULT_SHOW_SUGGESTED_QS

# Sidebar - show toggles before auth (disabled after)
with st.sidebar:
    # Setup options - locked after auth
    st.subheader("Setup Options")
    disabled = st.session_state.authenticated
    if disabled:
        st.caption("*Reload page to change*")
    
    st.session_state.opt_auth = st.toggle(
        "Authentication (DLS)", 
        value=st.session_state.opt_auth, 
        disabled=disabled
    )
    st.session_state.opt_guardrails = st.toggle(
        "Guardrail Checks", 
        value=st.session_state.opt_guardrails, 
        disabled=disabled
    )
    
    st.divider()
    
    # Display options - always editable
    st.subheader("Display Options")
    st.session_state.opt_references = st.toggle(
        "Show References", 
        value=st.session_state.opt_references
    )
    st.session_state.opt_suggested_qs = st.toggle(
        "Show Suggested Questions", 
        value=st.session_state.opt_suggested_qs
    )
    
    st.divider()
    
    # User info (after auth)
    if st.session_state.user_name:
        st.write(f"**User:** {st.session_state.user_name}")
        groups = st.session_state.security_groups or []
        st.write(f"**Groups:** {len(groups)} group(s)")
        if groups:
            with st.expander("View Group IDs"):
                for group_id in groups:
                    st.code(group_id, language=None)
        elif st.session_state.opt_auth:
            st.warning("No groups found. Check App Registration token config.")
    
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Authentication
if st.session_state.opt_auth and not st.session_state.authenticated:
    st.info("Please authenticate to continue.")
    if st.button("🔐 Login with Microsoft"):
        try:
            groups, user_name = authenticate_user()
            st.session_state.security_groups = groups
            st.session_state.user_name = user_name
            st.session_state.authenticated = True
            st.rerun()
        except Exception as e:
            st.error(f"Authentication failed: {e}")
    st.stop()

# Mark as authenticated if auth is disabled (bypass)
if not st.session_state.opt_auth:
    st.session_state.authenticated = True
    st.session_state.security_groups = None  # None = bypass DLS

# Welcome message on first load
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown("Hello! I'm your RAG assistant. How can I help you today?")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if st.session_state.opt_references and "references" in message and message["references"]:
            with st.expander("📚 References"):
                for ref in message["references"]:
                    st.markdown(f"**[{ref['id']}]** {ref['text']}")
        if st.session_state.opt_suggested_qs and "suggested_questions" in message and message["suggested_questions"]:
            with st.expander("💡 Suggested Questions"):
                for sq in message["suggested_questions"]:
                    st.markdown(f"- {sq['text']}")

# Chat input
if prompt := st.chat_input("Ask a question..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Check guardrails first
    guardrail_triggered = False
    if st.session_state.opt_guardrails:
        try:
            response = requests.post(f"{API_BASE_URL}/guardrails", json={"query": prompt})
            response.raise_for_status()
            guardrail_result = response.json()
            guardrail_triggered = guardrail_result.get("guardrail_triggered", False)
            if guardrail_triggered:
                answer = guardrail_result.get("guardrail_answer", "Content blocked.")
                st.session_state.messages.append({"role": "assistant", "content": answer})
                with st.chat_message("assistant"):
                    st.markdown(answer)
        except requests.RequestException as e:
            st.error(f"Guardrails API error: {e}")

    # Call chat API if guardrails passed
    if not guardrail_triggered:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Build chat history (last 12 messages)
                    chat_history = [{"role": m["role"], "content": m["content"]} 
                                    for m in st.session_state.messages[-12:]]
                    
                    response = requests.post(f"{API_BASE_URL}/chat", json={
                        "chat_history": chat_history,
                        "security_groups": st.session_state.security_groups
                    })
                    response.raise_for_status()
                    chat_response = response.json()
                    
                    answer = chat_response.get("assistant_message", {}).get("content", "")
                    references = chat_response.get("references", [])
                    suggested_questions = chat_response.get("suggested_questions", [])
                    
                    st.markdown(answer)
                    
                    if st.session_state.opt_references and references:
                        with st.expander("📚 References"):
                            for ref in references:
                                st.markdown(f"**[{ref['id']}]** {ref['text']}")
                    
                    if st.session_state.opt_suggested_qs and suggested_questions:
                        with st.expander("💡 Suggested Questions"):
                            for sq in suggested_questions:
                                st.markdown(f"- {sq['text']}")
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "references": references,
                        "suggested_questions": suggested_questions
                    })
                    
                except requests.RequestException as e:
                    st.error(f"Chat API error: {e}")
