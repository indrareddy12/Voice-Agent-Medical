import sys
import os

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.triage import check_emergency_triage
from app.rag import search_knowledge_base
from app.config import settings

def test_triage():
    print("Testing Clinical Triage Module...")
    # Safe query
    safe = check_emergency_triage("I want to book an appointment with Dr. Jenkins")
    assert not safe["is_emergency"], "Safe query flagged as emergency"
    print("[OK] Safe query passed")
    
    # Emergency query
    emergency = check_emergency_triage("Help! I am having sudden chest pain and my left arm feels numb!")
    assert emergency["is_emergency"], "Emergency query NOT flagged"
    print("[OK] Emergency query correctly flagged")
    print(f"Emergency message: {emergency['response'][:60]}...")

def test_rag():
    print("\nTesting RAG Retrieval Module...")
    docs = search_knowledge_base("who is Dr Jenkins?")
    assert len(docs) > 0, "No docs found"
    assert "Jenkins" in docs[0]["content"], "Incorrect doctor returned"
    print("[OK] Doctor FAQ search passed")
    
    hours_docs = search_knowledge_base("what time do you close on Friday?")
    assert "6:30" in hours_docs[0]["content"], "Incorrect clinic hours returned"
    print("[OK] Opening hours search passed")

if __name__ == "__main__":
    print(f"Running backend validation checks on Python {sys.version}...")
    print(f"App Settings: {settings.app_name} | Demo Mode: {settings.is_demo_mode}")
    try:
        test_triage()
        test_rag()
        print("\nAll backend logic checks PASSED successfully! [OK]")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        sys.exit(1)
