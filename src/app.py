"""
src/app.py — Phase 7: Streamlit User Interface

Provides a minimal, compliant chat UI for the Mutual Fund FAQ Assistant.
"""

import streamlit as st
import sys
import os

# Add the project root to sys.path so we can import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline import answer_query

# 1. Page Config
st.set_page_config(
    page_title="Mutual Fund FAQ Assistant",
    page_icon="📊",
    layout="centered"
)

# 2. Welcome Section
st.title("📊 Mutual Fund FAQ Assistant")
st.markdown("**Facts-only answers about HDFC mutual fund schemes.**")
st.warning("⚠️ **Facts-only. No investment advice.** This assistant provides objective information directly from official Groww mutual fund pages. It cannot recommend funds or predict future returns.")

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            # Display citations and footer if they exist
            if "citation" in message and message["citation"] != "N/A":
                st.caption(f"[View Source]({message['citation']})")
            if "footer" in message and message["footer"] != "N/A":
                st.caption(message["footer"])

# 3. Example Questions (Clickable chips)
st.write("---")
st.write("### Try asking:")

col1, col2, col3 = st.columns(3)
example_query = None

if col1.button("Expense ratio of HDFC Mid Cap?"):
    example_query = "What is the expense ratio of HDFC Mid Cap Fund?"
if col2.button("ELSS lock-in period?"):
    example_query = "What is the ELSS lock-in period?"
if col3.button("Exit load for Small Cap?"):
    example_query = "What is the exit load for HDFC Small Cap Fund?"

# 4. Chat Input
# Use the example query if a button was clicked, otherwise check the chat input
user_input = st.chat_input("Ask a factual question about mutual funds...")
query = example_query or user_input

if query:
    # Append and display user message
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)
        
    # Process the query through the pipeline
    with st.chat_message("assistant"):
        with st.spinner("Searching official sources..."):
            result = answer_query(query)
            
            answer = result.get("answer", "An error occurred.")
            citation = result.get("citation", "N/A")
            footer = result.get("footer", "N/A")
            
            # Display answer
            st.markdown(answer)
            if citation != "N/A":
                st.caption(f"[View Source]({citation})")
            if footer != "N/A":
                st.caption(footer)
                
    # Save assistant response to session state
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "citation": citation,
        "footer": footer
    })
