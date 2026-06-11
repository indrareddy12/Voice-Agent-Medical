import os
from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import re

# 1. Define the Graph State
class ReceptionistState(TypedDict):
    """The state variables carried across nodes in the LangGraph workflow."""
    # List of messages in the chat history
    messages: list[BaseMessage]
    
    # Slot filling fields for appointment scheduling
    patient_name: str | None
    patient_dob: str | None
    doctor_name: str | None
    appointment_reason: str | None
    
    # Tracking if booking was successfully written to the DB
    booking_status: str | None
    
    # Clinical safety override flag
    is_emergency: bool

# 2. Define the Graph Nodes

def safety_triage_node(state: ReceptionistState) -> Dict[str, Any]:
    """Node 1: Clinical safety scanner. Run first with zero-latency logic."""
    last_message = state["messages"][-1].content.lower()
    
    # Critical emergency indicators
    emergency_keywords = ["chest pain", "breathless", "numb", "bleeding", "stroke", "heart attack"]
    if any(k in last_message for k in emergency_keywords):
        return {
            "is_emergency": True,
            "messages": state["messages"] + [AIMessage(content="CRITICAL SAFETY INTERRUPT: Please dial 999 or go to the nearest A&E immediately.")]
        }
    
    return {"is_emergency": False}

def agent_reasoning_node(state: ReceptionistState) -> Dict[str, Any]:
    """Node 2: The LLM agent evaluates context, fills slots, and formats replies."""
    # Check for actual LLM API key (Google Gemini or OpenAI)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        # Fallback simulation of LLM dialogue slot-filling for demonstration ease
        return simulate_receptionist_response(state)
    
    # In production, we initialize our LangChain LLM provider:
    # from langchain_google_genai import ChatGoogleGenerativeAI
    # llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
    
    # Define system instruction with slot state
    system_prompt = (
        "You are Aura, the AI receptionist for Aura Medical Centre. "
        "To book, you must sequentially collect: Patient Name, DOB, Doctor, and Reason. "
        f"Current Slots: Name={state['patient_name']}, DOB={state['patient_dob']}, "
        f"Doctor={state['doctor_name']}, Reason={state['appointment_reason']}"
    )
    
    # (Simulated LLM call placeholder)
    response_content = "Hello, I am Aura. How can I help you today?"
    return {
        "messages": state["messages"] + [AIMessage(content=response_content)]
    }

def database_booking_node(state: ReceptionistState) -> Dict[str, Any]:
    """Node 3: Database transaction worker (Tool node)."""
    # Write to SQLite database using app's database module
    try:
        from app import database
        database.add_appointment(
            patient_name=state["patient_name"] or "Unknown",
            patient_dob=state["patient_dob"] or "Unknown",
            doctor_name=state["doctor_name"] or "Unknown",
            appointment_time="Tomorrow at 10:30 AM",
            reason=state["appointment_reason"] or "Routine Consultation"
        )
        return {"booking_status": "Success"}
    except Exception as e:
        return {"booking_status": f"Failed: {e}"}

# 3. Define the Routers (Conditional Edges)

def route_triage(state: ReceptionistState) -> str:
    """Determine routing based on clinical safety status."""
    if state["is_emergency"]:
        return "emergency_end"
    return "continue"

def route_next_step(state: ReceptionistState) -> str:
    """Determine whether to proceed to tool node (DB write) or end turn."""
    # If all slots are collected and appointment has not been written to DB yet:
    if (state["patient_name"] and 
        state["patient_dob"] and 
        state["doctor_name"] and 
        state["appointment_reason"] and 
        state["booking_status"] is None):
        return "book_to_db"
    
    return "wait_for_user"

# 4. Construct and Compile the State Graph
workflow = StateGraph(ReceptionistState)

# Add Nodes
workflow.add_node("safety_triage", safety_triage_node)
workflow.add_node("agent_reasoning", agent_reasoning_node)
workflow.add_node("database_booking", database_booking_node)

# Set Entry Point
workflow.set_entry_point("safety_triage")

# Define Routing Edges
workflow.add_conditional_edges(
    "safety_triage",
    route_triage,
    {
        "emergency_end": END,
        "continue": "agent_reasoning"
    }
)

workflow.add_conditional_edges(
    "agent_reasoning",
    route_next_step,
    {
        "book_to_db": "database_booking",
        "wait_for_user": END
    }
)

# Tool Node terminates to End
workflow.add_edge("database_booking", END)

# Compile the Graph
app = workflow.compile()


# --- Local Slot-Filling Simulation Helper ---
def simulate_receptionist_response(state: ReceptionistState) -> Dict[str, Any]:
    """Helper to simulate state slot filling without an active LLM API key."""
    last_message = state["messages"][-1].content.strip()
    
    new_state = {}
    # Simulate simple slot parsing
    if not state["patient_name"]:
        new_state["patient_name"] = last_message
        msg = f"Thank you, {last_message}. What is your date of birth?"
    elif not state["patient_dob"]:
        new_state["patient_dob"] = last_message
        msg = "Understood. Which doctor would you like to see? Dr. Alan Turing, Dr. Ryan Jenkins, or Dr. Sonia Ryan?"
    elif not state["doctor_name"]:
        new_state["doctor_name"] = last_message
        msg = f"Perfect. What is the brief reason for booking this appointment with {last_message}?"
    elif not state["appointment_reason"]:
        new_state["appointment_reason"] = last_message
        msg = "Excellent. I have scheduled that for you. Recording it in the GP reception ledger..."
    else:
        msg = "Hello, I am Aura. I can help you book an appointment. What is your full name?"
        
    new_state["messages"] = state["messages"] + [AIMessage(content=msg)]
    return new_state

if __name__ == "__main__":
    print("--------------------------------------------------")
    print("      LangGraph Medical Voice Agent Router        ")
    print("--------------------------------------------------")
    print("[OK] State Graph compilation successful!")
    print("Nodes registered: 'safety_triage', 'agent_reasoning', 'database_booking'")
    print("Edges compiled with conditional routers.")
    print("\nThis file is ready for use as a standalone interview reference.")
    print("--------------------------------------------------")
