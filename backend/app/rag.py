import re
from typing import Dict, List, Any

# Mock Knowledge Base Documents
CLINIC_DOCUMENTS = [
    {
        "id": "general_info",
        "title": "Clinic Name, Address, and Contact",
        "keywords": ["name", "address", "phone", "number", "tel", "contact", "where", "location", "email", "postcode"],
        "content": "Aura Medical Centre is located at 12 Medical Way, Manchester, M1 3BE. Our phone number is 0161 999 8888. Email: admin@auramedical.nhs.uk."
    },
    {
        "id": "opening_hours",
        "title": "Opening Hours and Out of Hours",
        "keywords": ["hours", "open", "close", "time", "saturday", "sunday", "weekend", "night", "evening", "friday"],
        "content": "Aura Medical Centre is open Monday to Friday, from 8:00 AM to 6:30 PM. We are closed on Saturdays and Sundays. For medical assistance when we are closed, please call NHS 111."
    },
    {
        "id": "doctors_schedule",
        "title": "Doctor Schedules and Specialities",
        "keywords": ["doctor", "gp", "schedule", "dr", "jenkins", "ryan", "sonia", "turing", "who", "specialist", "pediatrician", "cardiologist"],
        "content": (
            "We have three GPs: \n"
            "1. Dr. Alan Turing (General Practitioner) - available Monday through Friday.\n"
            "2. Dr. Ryan Jenkins (Cardiologist & General Practice) - available Monday, Wednesday, and Friday.\n"
            "3. Dr. Sonia Ryan (Pediatrician & General Practice) - available Tuesday and Thursday."
        )
    },
    {
        "id": "registration",
        "title": "New Patient Registration",
        "keywords": ["register", "join", "new", "patient", "sign", "gms1", "form"],
        "content": "To register as a new patient, you can fill out the online registration form on our website, or collect a paper GMS1 registration form from reception. You must live within our catchment area."
    },
    {
        "id": "prescriptions",
        "title": "Repeat Prescriptions",
        "keywords": ["prescription", "repeat", "medication", "medicine", "order", "pharmacy"],
        "content": "You can request repeat prescriptions via the NHS App, our website, or by submitting a paper slip in the repeat prescription box at reception. Please allow 2 full working days for processing."
    },
    {
        "id": "test_results",
        "title": "Blood and Test Results",
        "keywords": ["test", "results", "blood", "x-ray", "urine", "lab", "check"],
        "content": "To get your test results, please call the surgery after 2:00 PM Monday-Friday when phone lines are quieter, or view them directly on your NHS App account."
    },
    {
        "id": "vaccinations",
        "title": "Travel and Flu Vaccinations",
        "keywords": ["vaccine", "vaccination", "flu", "travel", "jab", "shot", "travel health"],
        "content": "We offer NHS flu jabs to eligible patients and travel vaccinations. For travel vaccines, please complete a travel questionnaire on our website at least 6 weeks before you travel."
    }
]

# Common English stopwords to prevent false-positive matches in RAG retrieval
STOPWORDS = {
    "can", "our", "the", "and", "for", "you", "your", "are", "what", "how",
    "who", "with", "from", "have", "this", "that", "but", "not", "has", "about",
    "please", "would", "like", "want", "help", "some", "someone", "here", "there"
}

def search_knowledge_base(query: str, limit: int = 2) -> List[Dict[str, Any]]:
    """
    Simulates a vector-search RAG retrieval by scoring text overlap of query terms with document keywords and content.
    Returns the top-K relevant documents.
    """
    words = re.findall(r"\b\w{3,}\b", query.lower()) # words with 3+ characters
    # Filter out generic stopwords
    words = [w for w in words if w not in STOPWORDS]
    if not words:
        return []
        
    scored_docs = []
    for doc in CLINIC_DOCUMENTS:
        score = 0
        doc_text = f"{doc['title']} {doc['content']}".lower()
        
        # Match keywords (higher weight)
        for keyword in doc["keywords"]:
            if keyword in query.lower():
                score += 3
                
        # Match query words in document content
        for word in words:
            if word in doc_text:
                score += 1
                
        if score > 0:
            scored_docs.append((score, doc))
            
    # Sort by score descending
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    
    # Return documents
    results = [doc for _, doc in scored_docs]
    
    # Fallback to empty if nothing matched
    if not results:
        return []
        
    return results[:limit]
