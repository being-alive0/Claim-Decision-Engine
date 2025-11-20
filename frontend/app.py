import streamlit as st
import requests
import json

# --- Config ---
# FIX 1: Corrected the URL string
BACKEND_URL = "http://127.0.0.1:8000"

# FIX 2: Added the proxy bypass configuration
proxy_config = {
    "http": None,
    "https" : None,
}

# --- Page Setup ---
st.set_page_config(page_title="Policy Document Analyzer", layout="wide")
st.title("📄 Policy Document Analyzer")
st.markdown("Upload a policy PDF and ask questions to get structured, justified answers.")

# --- UI Components ---

# Column layout
col1, col2 = st.columns(2)

with col1:
    st.header("1. Upload Policy PDF")
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    
    if uploaded_file is not None:
        with st.spinner("Processing document... This may take a moment."):
            # Prepare file for API request
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            
            try:
                # Send to backend's /upload endpoint
                response = requests.post(
                    f"{BACKEND_URL}/upload", 
                    files=files, 
                    timeout=600,
                    proxies=proxy_config  # <-- FIX 2 Applied here
                )
                
                if response.status_code == 200:
                    st.success("✅ Document processed and ready for questions!")
                    st.session_state.doc_ready = True
                else:
                    st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
                    st.session_state.doc_ready = False
            except requests.exceptions.RequestException as e:
                st.error(f"Failed to connect to backend: {e}")
                st.session_state.doc_ready = False

with col2:
    st.header("2. Ask a Question")
    
    # Check if a document has been processed
    if st.session_state.get("doc_ready", False):
        query = st.text_input("Enter your query (e.g., '46M, knee surgery, 3-month policy')")

        if st.button("Get Answer"):
            if query:
                with st.spinner("Analyzing..."):
                    try:
                        # Send to backend's /query endpoint
                        response = requests.post(
                            f"{BACKEND_URL}/query", 
                            json={"question": query},
                            proxies=proxy_config  # <-- FIX 2 Applied here
                        )
                        
                        if response.status_code == 200:
                            # Display the structured JSON response
                            st.subheader("Analysis Result:")
                            st.json(response.json())
                        else:
                            st.error(f"Error from backend: {response.json().get('detail', 'Unknown error')}")
                    
                    except requests.exceptions.RequestException as e:
                        st.error(f"Failed to connect to backend: {e}")
            else:
                st.warning("Please enter a query.")
    else:
        st.info("Please upload and process a document first.")