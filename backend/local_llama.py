import os
import shutil
import json
import gc
import time
import sys
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# --- Logging setup ---
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("doc_api")
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
if not log.hasHandlers():
    log.addHandler(ch)

# --- LangChain components for Ollama ---
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# --- Load environment variables ---
load_dotenv()

# --- App setup ---
app = FastAPI(title="Document Processing API (Local Ollama)")

# --- Storage setup ---
UPLOAD_DIR = "./temp_uploads"
VECTOR_STORE_DIR = "./faiss_db"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)

# --- Models ---
class QueryModel(BaseModel):
    question: str

class QueryResponse(BaseModel):
    decision: str
    amount: int
    justification: list

# --- LLM + Embedding setup using Ollama ---
embeddings = OllamaEmbeddings(model="nomic-embed-text")
llm = ChatOllama(model="llama3", temperature=0)

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

# --- Helper function ---
def force_delete_directory(path):
    if not os.path.exists(path):
        return
    retries = 5
    delay = 0.5
    for i in range(retries):
        try:
            shutil.rmtree(path)
            return
        except PermissionError as e:
            if "WinError 32" in str(e) and i < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise e
        except Exception as e:
            raise e

# --- Endpoints ---
@app.post("/upload")
async def upload_and_process_pdf(file: UploadFile = File(...)):
    file_path = None
    try:
        force_delete_directory(VECTOR_STORE_DIR)
        os.makedirs(VECTOR_STORE_DIR, exist_ok=True)

        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        loader = PyPDFLoader(file_path)
        documents = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        chunks = text_splitter.split_documents(documents)

        vectorstore = FAISS.from_documents(documents=chunks, embedding=embeddings)
        vectorstore.save_local(VECTOR_STORE_DIR)

        return {"status": "success", "message": f"File '{file.filename}' processed successfully."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

@app.post("/query", response_model=QueryResponse)
async def query_document(query: QueryModel):
    log.debug(f"--- Received query for: {query.question} ---")
    try:
        if not os.path.exists(VECTOR_STORE_DIR):
            log.warning("Vector store not found.")
            raise HTTPException(status_code=400, detail="No document uploaded yet.")

        log.debug("Loading FAISS vector store from disk...")
        vectorstore = FAISS.load_local(
            VECTOR_STORE_DIR,
            embeddings=embeddings,
            allow_dangerous_deserialization=True
        )
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

        rag_chain = (
            {"context": retriever, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )

        raw_response = rag_chain.invoke(query.question)
        log.debug(f"Received raw response:\n{raw_response}")

        del retriever
        del vectorstore
        gc.collect()

        try:
            if "json" in raw_response:
                raw_response = raw_response.split("json\n")[1].split("```")[0]
            json_response = json.loads(raw_response)
            return json_response
        except json.JSONDecodeError as json_err:
            log.error(f"FAILED TO PARSE JSON. Raw: {raw_response}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error parsing LLM response. Raw: {raw_response}")

    except Exception as e:
        log.error(f"UNEXPECTED ERROR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error during query: {str(e)}")