import os
import time
import re
import uuid
from typing import Dict, List, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.triage import check_emergency_triage
from app.rag import search_knowledge_base
from app.tts import generate_speech_file, cleanup_old_audio_files

# Setup FastAPI App
app = FastAPI(title=settings.app_name)

# Enable CORS for frontend interactions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For demo development ease
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Database and startup hook
from app import database

@app.on_event("startup")
def on_startup():
    database.init_db()

TELEMETRY_LOGS: List[Dict[str, Any]] = []
SESSION_STATES: Dict[str, Dict[str, Any]] = {}

# Ensure static directories exist and mount them
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(os.path.join(STATIC_DIR, "audio"), exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

# Request/Response schemas
class ChatRequest(BaseModel):
    text: str
    session_id: str
    voice_type: str = "female"

class AppointmentCreate(BaseModel):
    patient_name: str
    patient_dob: str
    doctor_name: str
    appointment_time: str
    reason: str

# Helper to log metrics
def log_telemetry(
    input_text: str,
    output_text: str,
    is_emergency: bool,
    latency_breakdown: Dict[str, float],
    tokens: int = 0
):
    log_entry = {
        "id": str(uuid.uuid4())[:8],
        "timestamp": time.strftime("%H:%M:%S"),
        "input": input_text,
        "output": output_text,
        "is_emergency": is_emergency,
        "latency": latency_breakdown,  # dict containing rag, llm, tts, total in ms
        "tokens": tokens
    }
    TELEMETRY_LOGS.insert(0, log_entry)
    # Keep last 20
    if len(TELEMETRY_LOGS) > 20:
        TELEMETRY_LOGS.pop()

# LLM integration calls
async def call_gemini(prompt: str) -> str:
    from google import genai
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text

async def call_openai(prompt: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content

# State Machine for local fallback (Demo Mode)
def handle_demo_booking(session_id: str, text: str, matched_faq: str | None = None) -> tuple[str, bool]:
    """
    State machine for booking flow in Demo Mode.
    Returns: (response_text, booking_triggered)
    """
    state = SESSION_STATES.setdefault(session_id, {
        "state": "idle",
        "name": "",
        "dob": "",
        "doctor": "",
        "reason": "",
        "proposed_time": "",
        "rejected_times": []
    })
    
    text_lower = text.lower()
    
    # If the user asks a question and we aren't in active booking, answer the question.
    # Or, if they ask a question, we let FAQ interrupt unless we are collecting info.
    if matched_faq and state["state"] == "idle":
        return matched_faq, False
        
    # Cancel request
    if "cancel" in text_lower or "start over" in text_lower:
        SESSION_STATES[session_id] = {
            "state": "idle", "name": "", "dob": "", "doctor": "", "reason": "", "proposed_time": "", "rejected_times": []
        }
        return "Of course, I have cancelled the booking process. How else can I help you today?", False

    current_state = state["state"]
    
    if current_state == "idle":
        if any(w in text_lower for w in ["book", "appointment", "schedule", "gp", "doctor", "see someone"]):
            # Check if doctor specified
            doctor = ""
            if "turing" in text_lower:
                doctor = "Dr. Alan Turing"
            elif "jenkins" in text_lower:
                doctor = "Dr. Ryan Jenkins"
            elif "sonia" in text_lower or "patel" in text_lower:
                doctor = "Dr. Sonia Ryan"
                
            state["state"] = "awaiting_name"
            if doctor:
                state["doctor"] = doctor
                return f"I can help you book an appointment with {doctor}. To start, could you please tell me your full name?", False
            else:
                return "I can certainly help you book a GP appointment. To get started, could you please tell me your full name?", False
        
        # General response if not matching FAQs or booking
        if matched_faq:
            return matched_faq, False
        return "Hello, I am Aura, your GP voice assistant. I can help you book an appointment or answer questions about repeat prescriptions, registration, and hours. What can I do for you today?", False
        
    elif current_state == "awaiting_name":
        # Extract name (simple fallback: take the whole sentence, or strip greeting)
        name = text.strip()
        name = re.sub(r"^(my name is|i am|this is|call me)\s+", "", name, flags=re.IGNORECASE)
        state["name"] = name
        state["state"] = "awaiting_dob"
        return f"Thank you, {name}. What is your date of birth?", False
        
    elif current_state == "awaiting_dob":
        dob = text.strip()
        state["dob"] = dob
        if state["doctor"]:
            state["state"] = "awaiting_reason"
            return f"Understood. And what is the brief reason for booking this appointment with {state['doctor']}?", False
        else:
            state["state"] = "awaiting_doctor"
            return "Thank you. Which doctor would you like to see? We have Dr. Alan Turing (GP), Dr. Ryan Jenkins (Cardiologist), or Dr. Sonia Ryan (Pediatrician).", False
            
    elif current_state == "awaiting_doctor":
        doctor_input = text_lower
        doctor = ""
        if "turing" in doctor_input:
            doctor = "Dr. Alan Turing"
        elif "jenkins" in doctor_input:
            doctor = "Dr. Ryan Jenkins"
        elif "sonia" in doctor_input or "patel" in doctor_input or "pediatrician" in doctor_input:
            doctor = "Dr. Sonia Ryan"
        else:
            return "Sorry, I didn't quite catch that. Would you like to see Dr. Turing, Dr. Jenkins, or Dr. Sonia?", False
            
        state["doctor"] = doctor
        state["state"] = "awaiting_reason"
        return f"Perfect, Dr. {doctor.split()[-1]}. What is the brief reason for this appointment?", False
        
    elif current_state == "awaiting_reason":
        reason = text.strip()
        state["reason"] = reason
        doctor = state["doctor"]
        
        # Calculate proposed time slot
        slot = database.get_next_available_slot(doctor)
        state["proposed_time"] = slot
        state["state"] = "awaiting_time_confirmation"
        
        return f"I have an available slot with {doctor} {slot.lower()}. Would that work for you?", False

    elif current_state == "awaiting_time_confirmation":
        text_lower = text.lower()
        # Simple keywords for agreement
        affirmatives = ["yes", "yeah", "sure", "ok", "fine", "work", "confirm", "yep", "correct"]
        
        if any(w in text_lower for w in affirmatives):
            # User accepted! Commit booking
            name = state["name"]
            dob = state["dob"]
            doctor = state["doctor"]
            reason = state["reason"]
            proposed_time = state["proposed_time"]
            
            # Clear state
            SESSION_STATES[session_id] = {
                "state": "idle", "name": "", "dob": "", "doctor": "", "reason": "", "proposed_time": "", "rejected_times": []
            }
            
            response = (
                f"Excellent, {name}. I have successfully scheduled a routine appointment for you with {doctor} for {proposed_time.lower()}. "
                f"You will receive a confirmation SMS shortly. [BOOK_APPOINTMENT: Name: {name} | DOB: {dob} | Doctor: {doctor} | Reason: {reason} | Time: {proposed_time}]"
            )
            return response, True
            
        else:
            # User rejected! Propose next available slot
            doctor = state["doctor"]
            state["rejected_times"].append(state["proposed_time"])
            
            new_slot = database.get_next_available_slot(doctor, ignore_slots=state["rejected_times"])
            state["proposed_time"] = new_slot
            
            return f"No problem. How about {new_slot.lower()} instead?", False

    return "Sorry, I got confused. Let's start over. How can I help you?", False

# Main Endpoint: Chat process (handles clinical triage, RAG search, LLM reasoning, TTS synthesis)
@app.post("/api/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    t_triage_start = time.time()
    
    # 1. Clinical Safety Triage check (Instant override)
    triage_result = check_emergency_triage(request.text)
    t_triage_ms = (time.time() - t_triage_start) * 1000
    
    if triage_result["is_emergency"]:
        t_tts_start = time.time()
        audio_file = await generate_speech_file(triage_result["response"], request.voice_type)
        t_tts_ms = (time.time() - t_tts_start) * 1000
        
        total_ms = (time.time() - start_time) * 1000
        log_telemetry(
            input_text=request.text,
            output_text=triage_result["response"],
            is_emergency=True,
            latency_breakdown={
                "triage": round(t_triage_ms, 1),
                "rag": 0.0,
                "llm": 0.0,
                "tts": round(t_tts_ms, 1),
                "total": round(total_ms, 1)
            }
        )
        background_tasks.add_task(cleanup_old_audio_files)
        return {
            "response": triage_result["response"],
            "audio_url": f"/static/audio/{audio_file}",
            "is_emergency": True,
            "session_state": "idle",
            "booking_details": None
        }

    # 2. Retrieve FAQ RAG Context
    t_rag_start = time.time()
    rag_docs = search_knowledge_base(request.text, limit=1)
    rag_context = rag_docs[0]["content"] if rag_docs else ""
    t_rag_ms = (time.time() - t_rag_start) * 1000
    
    # 3. LLM or State Machine generation
    t_llm_start = time.time()
    response_text = ""
    booking_triggered = False
    tokens_estimate = 0
    
    if settings.is_demo_mode:
        # Run state machine
        response_text, booking_triggered = handle_demo_booking(request.session_id, request.text, rag_context)
        t_llm_ms = (time.time() - t_llm_start) * 1000
        tokens_estimate = len(request.text.split()) + len(response_text.split())
    else:
        # LLM execution (Gemini or OpenAI)
        system_prompt = (
            "You are Aura, the warm and professional AI medical receptionist for Aura Medical Centre.\n"
            "Keep your responses spoken-friendly and CONCISE (1 to 3 sentences max). Do not use markdown tags, bullet points, or bold text (*).\n\n"
            "CLINICAL SAFETY:\n"
            "If the user mentions emergency signs (chest pain, stroke, breathlessness, bleeding), immediately stop and redirect: 'Please call 999 or go to A&E immediately.'\n\n"
            "APPOINTMENT BOOKING FLOW:\n"
            "We have three doctors:\n"
            "1. Dr. Alan Turing (GP, Mon-Fri)\n"
            "2. Dr. Ryan Jenkins (Cardiologist, Mon/Wed/Fri)\n"
            "3. Dr. Sonia Ryan (Pediatrician, Tue/Thu)\n\n"
            "To book, you must sequentially collect: (1) Patient Name, (2) Date of Birth (DOB), (3) Doctor Name, (4) Reason.\n"
            "Once you have all 4 items, propose the next available slot for that doctor and ask the patient if that time works. "
            "Only output the confirmation tag once they explicitly confirm/accept the proposed time:\n"
            "[BOOK_APPOINTMENT: Name: <name> | DOB: <dob> | Doctor: <doctor> | Reason: <reason> | Time: <confirmed_time>]\n\n"
            f"KNOWLEDGE CONTEXT:\n{rag_context}\n"
            "Answer patient questions using the knowledge context. If the query is unrelated, keep them on track with bookings or surgery services."
        )
        
        full_prompt = f"System:\n{system_prompt}\n\nPatient: {request.text}\n\nAura:"
        
        try:
            if settings.openai_api_key:
                response_text = await call_openai(full_prompt)
            else:
                response_text = await call_gemini(full_prompt)
                
            if "[BOOK_APPOINTMENT:" in response_text:
                booking_triggered = True
                
            t_llm_ms = (time.time() - t_llm_start) * 1000
            tokens_estimate = int((len(system_prompt) + len(request.text) + len(response_text)) / 4)
        except Exception as e:
            # Fallback to demo mode if LLM fails (e.g. rate limit / network error)
            print(f"LLM Error, falling back to state machine: {e}")
            response_text, booking_triggered = handle_demo_booking(request.session_id, request.text, rag_context)
            t_llm_ms = (time.time() - t_llm_start) * 1000
            tokens_estimate = len(request.text.split()) + len(response_text.split())

    # 4. Handle booking extraction and DB storage
    booking_details = None
    if booking_triggered:
        match = re.search(r"\[BOOK_APPOINTMENT:\s*Name:\s*(.*?)\s*\|\s*DOB:\s*(.*?)\s*\|\s*Doctor:\s*(.*?)\s*\|\s*Reason:\s*(.*?)(?:\s*\|\s*Time:\s*(.*?))?\s*\]", response_text)
        if match:
            doc_name = match.group(3).strip()
            # If Time is specified in the tag, use it. Otherwise, calculate next available slot
            appt_time = match.group(5).strip() if match.group(5) else database.get_next_available_slot(doc_name)
            
            booking_details = database.add_appointment(
                patient_name=match.group(1).strip(),
                patient_dob=match.group(2).strip(),
                doctor_name=doc_name,
                appointment_time=appt_time,
                reason=match.group(4).strip()
            )
            # Replace default 10:30 AM mention in the LLM response text if any
            response_text = re.sub(
                r"tomorrow at 10:30\s*(?:AM|PM)?",
                appt_time.lower(),
                response_text,
                flags=re.IGNORECASE
            )

    # 5. Generate Text-to-Speech audio file
    t_tts_start = time.time()
    # Strip booking tag from text spoken by speech synth
    clean_speech_text = re.sub(r"\[BOOK_APPOINTMENT:.*?\]", "", response_text).strip()
    audio_file = await generate_speech_file(clean_speech_text, request.voice_type)
    t_tts_ms = (time.time() - t_tts_start) * 1000
    
    # Calculate Total Latency
    total_ms = (time.time() - start_time) * 1000

    # 6. Log Telemetry
    log_telemetry(
        input_text=request.text,
        output_text=clean_speech_text,
        is_emergency=False,
        latency_breakdown={
            "triage": round(t_triage_ms, 1),
            "rag": round(t_rag_ms, 1),
            "llm": round(t_llm_ms, 1),
            "tts": round(t_tts_ms, 1),
            "total": round(total_ms, 1)
        },
        tokens=tokens_estimate
    )
    
    # Trigger background cleanup of files
    background_tasks.add_task(cleanup_old_audio_files)
    
    # Retrieve current session state key
    curr_state = SESSION_STATES.get(request.session_id, {}).get("state", "idle")
    
    return {
        "response": clean_speech_text,
        "audio_url": f"/static/audio/{audio_file}",
        "is_emergency": False,
        "session_state": curr_state,
        "booking_details": booking_details
    }

# Endpoint: Get appointments
@app.get("/api/appointments")
def get_appointments(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return database.get_appointments()

# Endpoint: Create booking manually
@app.post("/api/appointments")
def create_appointment(appt: AppointmentCreate):
    return database.add_appointment(
        patient_name=appt.patient_name,
        patient_dob=appt.patient_dob,
        doctor_name=appt.doctor_name,
        appointment_time=appt.appointment_time,
        reason=appt.reason
    )

# Endpoint: Get telemetry logs
@app.get("/api/telemetry")
def get_telemetry(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return {
        "logs": TELEMETRY_LOGS,
        "summary": {
            "total_calls": len(TELEMETRY_LOGS),
            "emergencies": sum(1 for log in TELEMETRY_LOGS if log["is_emergency"]),
            "average_latency": round(sum(log["latency"]["total"] for log in TELEMETRY_LOGS) / len(TELEMETRY_LOGS), 1) if TELEMETRY_LOGS else 0.0
        }
    }

# Endpoint: Reset databases
@app.get("/api/reset")
def reset_system():
    global TELEMETRY_LOGS, SESSION_STATES
    database.clear_db()
    TELEMETRY_LOGS.clear()
    SESSION_STATES.clear()
    return {"status": "success", "message": "System database reset to initial states."}
