📄 AI-Powered Policy Document AnalyzerA robust Retrieval-Augmented Generation (RAG) system designed to automate the analysis of insurance policy documents. This application uses Large Language Models (LLMs) to interpret complex policy PDFs and provide structured, auditable decisions for claims processing.🚀 OverviewProcessing insurance claims manually is slow and error-prone. This system allows users to upload a policy document (PDF) and ask natural language queries about coverage (e.g., "Is a 46-year-old covered for knee surgery with a 3-month policy?").The system retrieves the exact relevant clauses from the document, evaluates the claim based only on those clauses, and returns a JSON response containing the decision (Approved/Rejected), eligible amount, and a justification citing the specific policy text.✨ Key Features📄 PDF Ingestion: Upload and process complex unstructured PDF policy documents.🧠 Semantic Search: Uses vector embeddings to find relevant clauses based on meaning, not just keywords (e.g., understands that "operation" relates to "surgery").🤖 AI Reasoning: Powered by LLMs to perform logical evaluations (comparing dates, age limits, and exclusions).✅ Structured Output: Returns a clean JSON object suitable for integration with downstream claims systems.🔍 Auditable Justification: Every decision is backed by specific text excerpts from the original document.🛠️ Tech StackLanguage: Python 3.10+Backend: FastAPI (High-performance API framework)Frontend: Streamlit (Interactive web interface)AI Orchestration: LangChainVector Database: ChromaDB (Persistent local storage)LLM & Embeddings: Google Gemini Pro & Google Generative AI EmbeddingsPDF Processing: PyPDF📂 Project Structuredoc_processor/
├── backend/
│   ├── main.py          # FastAPI backend application
│   └── ...
├── frontend/
│   ├── app.py           # Streamlit frontend application
│   └── ...
├── chroma_db/           # Local vector database storage (auto-generated)
├── temp_uploads/        # Temporary storage for uploaded files (auto-generated)
├── .env                 # API keys configuration
├── requirements.txt     # Python dependencies
└── README.md            # Project documentation
⚙️ Installation & SetupPrerequisitesPython 3.10 or higher installed.A Google AI Studio API Key (Get one here).1. Clone the Repositorygit clone <your-repo-url>
cd doc_processor
2. Install DependenciesIt is recommended to use a virtual environment.# Create virtual environment (optional but recommended)
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
3. Configure Environment VariablesCreate a .env file in the root directory and add your API key:GOOGLE_API_KEY="your_google_api_key_here"
🏃‍♂️ Running the ApplicationYou need to run the Backend and Frontend in two separate terminals.Terminal 1: Start the Backend APIuvicorn backend.main:app --reload
Wait until you see: Application startup complete.Terminal 2: Start the Frontend Interfacestreamlit run frontend/app.py
The application should automatically open in your browser at http://localhost:8501.📝 Usage GuideUpload Policy: On the left panel of the web app, click "Browse files" and select your policy PDF.Wait for Processing: The system will chunk and index the document. Wait for the "✅ Document processed" message.Ask a Query: In the right panel, enter a claim scenario.Example: 46M, knee surgery, Pune, 3-month policyView Results: The system will display the analysis in a structured JSON format, showing the decision and the specific clauses used to reach that conclusion.🧩 Troubleshooting[WinError 32] The process cannot access the file: This is a file locking issue on Windows. The application includes robust retry logic to handle this, but if it persists, ensure no other program (like VS Code's file explorer) has the chroma_db folder open.Connection Refused: Ensure the backend (Terminal 1) is running before you try to use the frontend.📜 LicenseThis project is open-source and available under the MIT License.