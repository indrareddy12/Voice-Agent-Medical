# Aura - AI Medical Voice Agent Receptionist Sandbox

Aura is a high-performance, interactive AI medical receptionist voice agent sandbox built for **Aura Medical Centre**. The application combines clinical safety triage guardrails, a local RAG knowledge base, LLM conversational intelligence, and edge-synthesized speech delivery. 

It is designed to demonstrate GDPR compliance (with PII anonymization in ledgers) and observability metrics (MLOps latency logging).

---

## 🚀 Key Features

* **Clinical Safety Triage Guardrail:** A zero-latency regex-based triage node intercepts emergency signs (e.g. chest pain, breathing difficulties) prior to LLM/RAG checks, bypassing standard booking to redirect patients to emergency services (dialing 999).
* **Hands-Free Continuous Voice Loop:** Eliminates tedious push-to-talk buttons. Once a voice session is started, Aura automatically restarts the speech-to-text recording engine as soon as the synthesized voice output finishes speaking, allowing for hands-free natural dialogue.
* **Dual-Input Multi-Modal Fallback:** Includes a dark glassmorphic text input field. If a user's browser fails to connect to cloud transcription servers (triggering Web Speech API `"network"` or `"not-allowed"` errors), the system alerts the user and falls back to text.
* **Observability & MLOps Latency Panel:** Real-time telemetry tracking breakdown (Triage scan, FAQ RAG search, LLM dialogue, and TTS synthesis in milliseconds).
* **Dynamic Slot Scheduling & Double-Booking Prevention:** SQLite-backed appointment ledger that queries active records and dynamically schedules the first available 30-minute daily slot for the selected practitioner.
* **GDPR & Privacy Compliance:** Toggleable **PII Anonymization** (obfuscates ledger logs, e.g. `I**** R*****`) and **Transient Audio Streams** (automatically deletes synthesized voice files on the server post-cleanup).

---

## 🛠️ Tech Stack
* **Backend:** FastAPI (Python), Uvicorn, SQLite3, `edge-tts` (Microsoft Edge Text-to-Speech), `google-genai` / `openai`
* **Frontend:** Vanilla HTML5, CSS3 Custom Properties (Dark glassmorphism theme), Vanilla JS (Web Speech API)

---

## 📁 Project Structure

```
voice-agent/
├── README.md                 # Project Overview & Guide (this file)
└── backend/
    ├── aura_clinic.db        # SQLite3 Database containing CRM ledger
    ├── requirements.txt      # Python dependencies list
    ├── test_backend.py       # Syntax and routing integration test suite
    ├── langgraph_example.py  # Standalone LangGraph architecture reference file
    ├── langgraph_workflow.md # Visual systems diagram explaining State Graph routing
    ├── static/               # Frontend Assets (FastAPI static mount)
    │   ├── index.html        # Glassmorphic user interface
    │   ├── index.css         # Styling system and visual states
    │   └── app.js            # STT, Audio Player, Web Sockets, and Telemetry Logic
    └── app/
        ├── config.py         # Base Settings & API key detection
        ├── database.py       # DB schema seed and slot scheduling logic
        ├── main.py           # FastAPI routes, state machine, and chat endpoint
        ├── rag.py            # Local FAQ knowledge retrieval
        ├── triage.py         # Zero-latency emergency triage checks
        └── tts.py            # Async Speech Synthesis & cleanup worker
```

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have **Python 3.10+** installed.

### 2. Environment Setup
Navigate into the `backend/` directory and configure your python virtual environment:
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. LLM API Configurations (Optional)
If you want to run the assistant using an active LLM, create a `.env` file in the `backend/` directory:
```env
GEMINI_API_KEY=your_gemini_key_here
# or
OPENAI_API_KEY=your_openai_key_here
```
*Note: If no API keys are configured, Aura automatically runs in deterministic local **Demo Mode** rule-based workflow.*

### 4. Running the Application
To launch the backend server locally:
```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open **Google Chrome** or **Microsoft Edge** and go to:
👉 [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 📊 LangGraph System Flow (Reference)

For study and scaling discussions, see [langgraph_workflow.md](./backend/langgraph_workflow.md).
```
[Start Input] ──> [Triage Node] ──is_emergency?──> Yes ──> [END - Warning]
                       │
                       No
                       ▼
             [LLM Reasoning Node] ──slots_complete?──> No  ──> [END - Wait]
                       │
                      Yes
                       ▼
             [Database Booking Node] ──> [END - Registered]
```
