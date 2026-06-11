import sqlite3
import os
from typing import List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aura_clinic.db")

def get_db_connection():
    """Returns a thread-safe connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Returns rows as dictionary-like objects
    return conn

def init_db():
    """Initializes the database schema and seeds it with default data if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create appointments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            patient_dob TEXT NOT NULL,
            doctor_name TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            reason TEXT NOT NULL
        )
    """)
    conn.commit()
    
    # Seed default appointments if database is empty
    cursor.execute("SELECT COUNT(*) FROM appointments")
    count = cursor.fetchone()[0]
    
    if count == 0:
        seed_data = [
            ("Eleanor Vance", "14/05/1974", "Dr. Ryan Jenkins", "Tomorrow at 09:30 AM", "Follow-up cardiology review"),
            ("Marcus Aurelius", "26/04/1961", "Dr. Alan Turing", "Tomorrow at 11:15 AM", "Routine hypertension check")
        ]
        cursor.executemany("""
            INSERT INTO appointments (patient_name, patient_dob, doctor_name, appointment_time, reason)
            VALUES (?, ?, ?, ?, ?)
        """, seed_data)
        conn.commit()
        
    conn.close()

def get_appointments() -> List[Dict[str, Any]]:
    """Retrieves all appointments from the database, ordered by ID ascending."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    
    # Convert sqlite3.Row objects to standard python dicts
    return [dict(row) for row in rows]

def add_appointment(patient_name: str, patient_dob: str, doctor_name: str, appointment_time: str, reason: str) -> Dict[str, Any]:
    """Inserts a new appointment row and returns the inserted record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO appointments (patient_name, patient_dob, doctor_name, appointment_time, reason)
        VALUES (?, ?, ?, ?, ?)
    """, (patient_name, patient_dob, doctor_name, appointment_time, reason))
    conn.commit()
    
    new_id = cursor.lastrowid
    conn.close()
    
    return {
        "id": str(new_id),
        "patient_name": patient_name,
        "patient_dob": patient_dob,
        "doctor_name": doctor_name,
        "appointment_time": appointment_time,
        "reason": reason
    }

def get_next_available_slot(doctor_name: str, ignore_slots: list[str] | None = None) -> str:
    """Finds the next available time slot for a given doctor to prevent double bookings."""
    potential_slots = [
        "Tomorrow at 09:00 AM",
        "Tomorrow at 09:30 AM",
        "Tomorrow at 10:00 AM",
        "Tomorrow at 10:30 AM",
        "Tomorrow at 11:00 AM",
        "Tomorrow at 11:30 AM",
        "Tomorrow at 01:30 PM",
        "Tomorrow at 02:00 PM",
        "Tomorrow at 02:30 PM",
        "Tomorrow at 03:00 PM",
        "Tomorrow at 03:30 PM",
        "Tomorrow at 04:00 PM"
    ]
    ignored = set(ignore_slots) if ignore_slots else set()
    conn = get_db_connection()
    cursor = conn.cursor()
    # Normalize query by stripping extra characters if any, but exact match is fine
    cursor.execute("SELECT appointment_time FROM appointments WHERE LOWER(doctor_name) LIKE ?", (f"%{doctor_name.lower().split()[-1]}%",))
    booked_slots = {row[0] for row in cursor.fetchall()}
    conn.close()
    
    for slot in potential_slots:
        if slot not in booked_slots and slot not in ignored:
            return slot
            
    return "Day after tomorrow at 09:00 AM"


def clear_db():
    """Wipes the database records and resets it to default seed data."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM appointments")
    conn.commit()
    conn.close()
    # Re-seed
    init_db()
