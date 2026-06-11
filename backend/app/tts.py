import os
import uuid
import edge_tts
import asyncio

# Directory to save temporary speech files
AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Recommended British neural voices
VOICES = {
    "female": "en-GB-SoniaNeural",  # Warm, professional NHS style
    "male": "en-GB-RyanNeural"      # Clear, calming
}

async def generate_speech_file(text: str, voice_type: str = "female") -> str:
    """
    Generates an MP3 file from text using edge-tts.
    Returns the filename of the generated audio.
    """
    voice = VOICES.get(voice_type, VOICES["female"])
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)
    
    # edge-tts communicate task
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filepath)
    
    return filename

def cleanup_old_audio_files(max_age_seconds: int = 300):
    """
    Cleans up temporary audio files older than max_age_seconds.
    Can be run as a background task.
    """
    import time
    try:
        now = time.time()
        for filename in os.listdir(AUDIO_DIR):
            filepath = os.path.join(AUDIO_DIR, filename)
            if os.path.isfile(filepath):
                # check file age
                file_age = now - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    os.remove(filepath)
    except Exception as e:
        print(f"Error during audio cleanup: {e}")
