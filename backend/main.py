import os
import shutil
import json
import gc
import time  # <-- 1. ADD THIS IMPORT
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import logging
import sys

logging.basicConfig(level=logging.DEBUG)

# LangChain components
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS


# Load environment variables (your API key)
from dotenv import load_dotenv
load_dotenv()

# --- App Setup ---
app = FastAPI(title="Document Processing API")

# --- Persistent Storage Setup ---
UPLOAD_DIR = "./temp_uploads"
VECTOR_STORE_DIR = "./chroma_db"

log = logging.getLogger("doc_api")
log.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)

if not log.hasHandlers():
    log.addHandler(ch)


# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)

# --- Pydantic Models ---
class QueryModel(BaseModel):
    question: str

class QueryResponse(BaseModel):
    decision: str
    amount: int
    justification: list

# --- Helper Functions & LLM Setup ---
embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0)

template = """
You are an expert insurance claims processor. Your task is to evaluate a user's query based ONLY on the provided policy clauses.
Do not use any external knowledge.
Provide your response in a structured JSON format with the following keys: "decision", "amount", and "justification".
The justification list should contain objects, each with a "finding" and "clause_text" key.
If an amount is not applicable, set it to 0.

CONTEXT (Policy Clauses):
{context}

QUERY:
{question}

JSON RESPONSE:
"""
prompt = ChatPromptTemplate.from_template(template)


# <-- 2. ADD THIS HELPER FUNCTION TO ROBUSTLY DELETE THE FOLDER -->
def force_delete_directory(path):
    """
    Robustly deletes a directory, retrying on Windows-specific file lock errors.
    """
    if not os.path.exists(path):
        return

    retries = 5
    delay = 0.5  # Start with a 500ms delay
    for i in range(retries):
        try:
            shutil.rmtree(path)
            # print(f"Successfully deleted {path}")
            return
        except PermissionError as e:
            if "WinError 32" in str(e) and i < retries - 1:
                # print(f"WinError 32, retrying in {delay}s... ({i+1}/{retries})")
                time.sleep(delay)
                delay *= 2  # Double the delay each time
            else:
                # print(f"Failed to delete {path} after {retries} retries.")
                raise e
        except Exception as e:
            raise e



@app.post("/upload")
async def upload_and_process_pdf(file: UploadFile = File(...)):
    """
    Handles PDF upload, processing, and vector store creation.
    This function overwrites any existing database.
    """
    file_path = None
    try:
        # <-- 3. USE THE NEW HELPER FUNCTION -->
        # Clear previous database and uploads robustly
        force_delete_directory(VECTOR_STORE_DIR)
        os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
        
        # Save the uploaded PDF temporarily
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        # 1. Load Document
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        # 2. Chunk Documents
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        chunks = text_splitter.split_documents(documents)

        # 3. Embed and Store in ChromaDB (persistently)
        vectorstore = FAISS.from_documents(
            documents=chunks,
            embedding=embeddings
        )
        # Save FAISS index to disk
        vectorstore.save_local(VECTOR_STORE_DIR)


        return {"status": "success", "message": f"File '{file.filename}' processed successfully."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    finally:
        # Clean up the temporary uploaded file
        if file_path and os.path.exists(file_path): # Check if file_path was assigned
            os.remove(file_path)

@app.post("/query", response_model=QueryResponse)
async def query_document(query: QueryModel):
    """
    Handles user queries against the processed vector store.
    """
    log.debug(f"--- Received query for: {query.question} ---") # <-- 3. Replaced print
    try:
        # 1. Load the existing vector store from disk
        log.debug("Checking if vector store exists...") # <-- Replaced print
        if not os.path.exists(VECTOR_STORE_DIR):
            log.warning("Vector store not found.")
            raise HTTPException(status_code=400, detail="No document has been uploaded and processed yet.")

        log.debug("Loading FAISS vector store from disk...")
        vectorstore = FAISS.load_local(
            VECTOR_STORE_DIR,
            embeddings=embeddings,
            allow_dangerous_deserialization=True
        )
        log.debug("FAISS vector store loaded successfully.")
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
        log.debug("Retriever created.") # <-- Replaced print

        # 3. Create RAG Chain
        log.debug("Creating RAG chain...") # <-- Replaced print
        rag_chain = (
            {"context": retriever, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )
        log.debug("RAG chain created.") # <-- Replaced print

        # 4. Invoke Chain and Get Response
        log.debug("Invoking RAG chain...") # <-- Replaced print
        raw_response = rag_chain.invoke(query.question)
        log.debug(f"Received raw response from LLM:\n{raw_response}") # <-- Replaced print
        
        # <-- 4. KEEP THIS BLOCK TO RELEASE LOCKS -->
        log.debug("Releasing vector store locks...") # <-- Replaced print
        del retriever
        del vectorstore
        gc.collect() 
        log.debug("Locks released.") # <-- Replaced print
        
        # 5. Parse the JSON string response from the LLM
        try:
            # Clean up potential markdown code fences
            log.debug("Cleaning LLM response...") # <-- Replaced print
            if "```json" in raw_response:
                raw_response = raw_response.split("```json\n")[1].split("```")[0]
                log.debug(f"Cleaned JSON string:\n{raw_response}") # <-- Replaced print
            
            log.debug("Parsing JSON string...") # <-- Replaced print
            json_response = json.loads(raw_response)
            log.debug("JSON parsed successfully.") # <-- Replaced print
            return json_response
            
        except json.JSONDecodeError as json_err:
            # --- THIS IS A VERY COMMON ERROR LOCATION ---
            # <-- 4. Use log.error with exc_info=True for stack trace -->
            log.error(
                f"FAILED TO PARSE JSON. Error: {json_err}\nRaw Response was: {raw_response}", 
                exc_info=True
            )
            raise HTTPException(status_code=500, detail=f"Error parsing LLM response. Raw: " + raw_response)

    except Exception as e:
        # --- THIS CATCHES ALL OTHER ERRORS ---
        # <-- 5. Use log.error here too -->
        log.error(
            f"AN UNEXPECTED ERROR OCCURRED. Error Type: {type(e)}\nError: {e}", 
            exc_info=True
        )
        # No need for traceback.print_exc() anymore
        raise HTTPException(status_code=500, detail=f"Error during query: {str(e)}")  
