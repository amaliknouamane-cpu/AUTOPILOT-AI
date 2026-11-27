# AutoPilot AI

AutoPilot AI is a sales and inventory automation project with an administrator dashboard and a separate client quotation workflow. It combines a Streamlit dashboard, a FastAPI service, PostgreSQL, and n8n. The administrator chatbot can read catalogue data, show a simple demand estimate, and answer questions from indexed business documents.

## Features

- Administrator dashboard for products, customers, quotations, and analytics.
- Client portal for quotation requests through manual selection, text, voice, or an uploaded product-list image.
- Existing quotation review and approval flow connected to the n8n workflow in `WORKFLOW/`.
- Admin chatbot with read-only product price and stock lookup, recent-sales demand estimates, and document-based policy answers.
- Local image text recognition with RapidOCR and ONNX Runtime; image extraction does not call the vision language model.
- LangGraph orchestration, an optional MCP server, and a small chatbot regression/evaluation suite.

## Requirements

- Python 3.12 or newer.
- PostgreSQL with the AutoPilot AI database tables/views configured.
- Ollama with the `llama3.2` model for general chatbot and document answers.
- n8n for the existing quotation automation and approval emails.

The repository does not currently include a PostgreSQL schema/migration file. The database configured in `DATABASE_URL` must already contain the tables and views expected by the dashboard and API.

## Setup on Windows

From the project root, create the virtual environment and install dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `DATABASE_URL` to the configured PostgreSQL database. Never share the real `.env` file, `admin_compte.txt`, or any login credentials with the project submission.

Install/start Ollama and make sure the configured chat model is available:

```powershell
ollama pull llama3.2
```

Start PostgreSQL, Ollama, and n8n. Import `WORKFLOW/AUTOPILOT AI(2).json` into n8n and configure its credentials and webhooks for your environment.

Run the dashboard in one terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

Run the FastAPI service in a second terminal:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

The n8n workflow expects the API at `http://127.0.0.1:8001` and the n8n webhook at `http://localhost:5678` by default.

## Chatbot knowledge documents

Place approved `.md`, `.txt`, or `.pdf` business documents in `backend/agentic_chat/knowledge/`, then rebuild the local index:

```powershell
.\.venv\Scripts\python.exe -m backend.agentic_chat.index_knowledge --lexical-only
```

The sample `demo_company_policy_draft.md` exists for chatbot demonstrations. Its delivery and return periods are illustrative proposals, not confirmed company rules; get the business owner's approval before using them with customers. The knowledge index excludes `README.md` files.

## Verification

Run the isolated chatbot regression checks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run the small end-to-end routing evaluation when PostgreSQL and Ollama are available:

```powershell
.\.venv\Scripts\python.exe -m backend.agentic_chat.run_evaluation
```

The evaluation fixture is a starter check, not a statistically representative AI quality benchmark.
