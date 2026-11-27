# AutoPilot AI chatbot module

This is a chatbot feature inside the existing AutoPilot AI dashboard, not a second
Streamlit application. The dashboard page is **AI Chatbot** in `dashboard/app.py`.
The original dashboard, database, quotation flow, and n8n workflow remain in place.

## Capabilities

- LangGraph supervisor routes requests to read-only inventory, forecast, and
  commercial-knowledge specialists. Quote requests are directed to Client Mode.
- Read-only business functions are exposed as MCP tools for compatible external hosts.
- Local RAG indexes only approved documents placed in `backend/agentic_chat/knowledge`
  and returns source filenames. It never reads generated customer quotation PDFs.
- Administrators cannot create or submit quotations from this chatbot. Customers use
  the existing Client Mode quotation flow and approval workflow.
- Observability records route, duration, outcome, and a one-way prompt fingerprint,
  not raw prompts. A small route-accuracy evaluation set is included.

## Setup

From the project root, install the chatbot-only dependencies into the existing venv:

```powershell
.venv\Scripts\python.exe -m pip install -r backend\agentic_chat\requirements.txt
```

Add the settings from `.env.example` to the root `.env` as needed. Keep the existing
`DATABASE_URL`. Start the usual PostgreSQL, Ollama, and n8n services, then start
the existing dashboard as before:

```powershell
.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

No V2 API or separate Streamlit process is required. To enable document answers,
place approved `.md`, `.txt`, or `.pdf` files in `knowledge/` and index them:

```powershell
.venv\Scripts\python.exe -m backend.agentic_chat.index_knowledge
```

To make the MCP tools available to an external MCP client, optionally run this
server in another terminal:

```powershell
.venv\Scripts\python.exe -m backend.agentic_chat.mcp_server
```

It listens on localhost at `http://127.0.0.1:8003/mcp`; do not expose it publicly
without authentication and network controls.

## Evaluation

Run the starter benchmark from the project root:

```powershell
.venv\Scripts\python.exe -m backend.agentic_chat.run_evaluation
```

It measures intent-routing accuracy and latency on a small editable fixture, not a
statistically representative quality benchmark. The transparent 30-day average
demand estimate is a baseline and does not replace the existing Chronos forecasts.
