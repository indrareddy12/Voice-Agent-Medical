// Session Management
const sessionId = Math.random().toString(36).substring(2, 15);
let isRecording = false;
let audioContext = null;
let currentAudio = null;
let recognition = null;
let isVoiceSession = false;

// DOM Elements
const micBtn = document.getElementById('mic-btn');
const voiceOrb = document.getElementById('voice-orb');
const waveformVisualizer = document.getElementById('waveform-visualizer');
const orbStatus = document.getElementById('orb-status');
const orbSubStatus = document.getElementById('orb-sub-status');
const voiceSelector = document.getElementById('voice-selector');
const transcriptBody = document.getElementById('transcript-body');
const clearLogBtn = document.getElementById('clear-log');
const appointmentsList = document.getElementById('appointments-list');
const logStream = document.getElementById('log-stream');
const resetDbBtn = document.getElementById('reset-db-btn');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

// Telemetry DOM
const safetyIndicator = document.getElementById('safety-indicator');
const safetyStatusVal = document.getElementById('safety-status-val');
const piiToggle = document.getElementById('pii-toggle');
const triageVal = document.getElementById('metric-triage-val');
const ragVal = document.getElementById('metric-rag-val');
const llmVal = document.getElementById('metric-llm-val');
const ttsVal = document.getElementById('metric-tts-val');
const totalVal = document.getElementById('metric-total-val');
const pbTriage = document.getElementById('pb-triage');
const pbRag = document.getElementById('pb-rag');
const pbLlm = document.getElementById('pb-llm');
const pbTts = document.getElementById('pb-tts');
const pbTotal = document.getElementById('pb-total');

// API Backend Base URL (Same Host in Production/Local mount)
const BASE_URL = window.location.origin;

// State Controller for Visuals
function setAgentState(state) {
    // Reset classes
    voiceOrb.className = 'voice-orb';
    waveformVisualizer.className = 'audio-waveform-visualizer';
    
    switch(state) {
        case 'listening':
            voiceOrb.classList.add('state-listening');
            waveformVisualizer.classList.add('listening');
            orbStatus.innerText = "Aura is Listening...";
            orbSubStatus.innerText = "Speak into your microphone now";
            break;
            
        case 'thinking':
            voiceOrb.classList.add('state-thinking');
            waveformVisualizer.classList.add('active');
            orbStatus.innerText = "Aura is Thinking...";
            orbSubStatus.innerText = "Consulting GP schedule & RAG knowledge base";
            break;
            
        case 'speaking':
            voiceOrb.classList.add('state-speaking');
            waveformVisualizer.classList.add('active');
            orbStatus.innerText = "Aura is Speaking";
            orbSubStatus.innerText = "Responding to patient query";
            break;
            
        case 'emergency':
            voiceOrb.classList.add('state-emergency');
            orbStatus.innerText = "CRITICAL EMERGENCY OVERRIDE";
            orbSubStatus.innerText = "Redirecting patient immediately to 999 / A&E";
            break;
            
        case 'idle':
        default:
            voiceOrb.classList.add('state-idle');
            orbStatus.innerText = "Aura is Idle";
            orbSubStatus.innerText = "Click the microphone button or test chips to begin";
            break;
    }
}

// Check & Initialize Speech Recognition
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        addSystemMessage("Speech Recognition API is not supported in this browser. Please use Google Chrome or Microsoft Edge. Falling back to typing / test chips.");
        orbSubStatus.innerText = "STT not supported - click chips to simulate";
        return;
    }
    
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-GB'; // British English for EMMA NHS theme
    
    recognition.onstart = () => {
        isRecording = true;
        isVoiceSession = true;
        micBtn.classList.add('recording');
        setAgentState('listening');
    };
    
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        addMessage('patient', transcript);
        sendQueryToAgent(transcript);
    };
    
    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        isVoiceSession = false;
        if (event.error === 'not-allowed') {
            addSystemMessage("Microphone permission denied. Please allow mic access in your browser settings, or use the text input below.");
        } else if (event.error === 'network') {
            addSystemMessage("Speech recognition network error: Cloud transcription services are unreachable. You can still type your query in the input box below!");
        } else {
            addSystemMessage(`Speech recognition error: ${event.error}. You can still type your query in the input box below!`);
        }
        stopRecordingVisuals();
    };
    
    recognition.onend = () => {
        stopRecordingVisuals();
    };
}

function stopRecordingVisuals() {
    isRecording = false;
    micBtn.classList.remove('recording');
    if (voiceOrb.classList.contains('state-listening')) {
        setAgentState('idle');
    }
}

// Play TTS Audio
async function playAudio(url) {
    // Stop any current audio
    if (currentAudio) {
        currentAudio.pause();
    }
    
    setAgentState('speaking');
    currentAudio = new Audio(url);
    
    currentAudio.onended = () => {
        setAgentState('idle');
        if (isVoiceSession && recognition) {
            recognition.start();
        }
    };
    
    currentAudio.onerror = (e) => {
        console.error("Audio playback error:", e);
        isVoiceSession = false;
        addSystemMessage("Error playing synthesized voice audio. Reviewing backend static logs.");
        setAgentState('idle');
    };
    
    try {
        await currentAudio.play();
    } catch(err) {
        console.warn("Autoplay blocked by browser. User interaction needed.", err);
        isVoiceSession = false;
        addSystemMessage("Click here to hear audio response (autoplay blocked).");
        // Create an overlay or let user know
        setAgentState('idle');
    }
}

// Send Text Query to FastAPI backend
async function sendQueryToAgent(text) {
    setAgentState('thinking');
    
    const voiceType = voiceSelector.value;
    
    try {
        const response = await fetch(`${BASE_URL}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: text,
                session_id: sessionId,
                voice_type: voiceType
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Add Aura text response
        addMessage('aura', data.response);
        
        // Handle emergency clinical override visual state
        if (data.is_emergency) {
            isVoiceSession = false;
            setAgentState('emergency');
            safetyIndicator.classList.add('emergency-triggered');
            safetyStatusVal.innerText = "EMERGENCY INTERRUPT";
            addSystemMessage("🚨 Clinical Safety Gate triggered. Booking bypassed. Instructed to dial 999.");
        } else {
            safetyIndicator.classList.remove('emergency-triggered');
            safetyStatusVal.innerText = "SAFE";
        }
        
        // Play speech file
        if (data.audio_url) {
            // Keep state speaking while audio plays (handled in playAudio)
            await playAudio(`${BASE_URL}${data.audio_url}`);
        } else {
            setAgentState('idle');
        }
        
        // If a booking details event is parsed, update the CRM database live
        if (data.booking_details) {
            addSystemMessage(`📅 Appointment booked successfully for patient: ${data.booking_details.patient_name}`);
            fetchAppointments();
        }
        
        // Update Telemetry Panel
        fetchTelemetry();
        
    } catch (error) {
        console.error("Backend connection failed:", error);
        isVoiceSession = false;
        addSystemMessage("Network connection to FastAPI server failed. Ensure server is running on port 8000.");
        setAgentState('idle');
    }
}

// Fetch GP Appointment Ledger CRM
async function fetchAppointments() {
    try {
        const response = await fetch(`${BASE_URL}/api/appointments?_=${Date.now()}`);
        const appts = await response.json();
        
        appointmentsList.innerHTML = '';
        if (appts.length === 0) {
            appointmentsList.innerHTML = '<div class="loading-placeholder">No appointments booked today.</div>';
            return;
        }
        
        // Check PII anonymization setting
        const anonymize = piiToggle.checked;
        
        appts.forEach(appt => {
            let name = appt.patient_name;
            let dob = appt.patient_dob;
            
            if (anonymize) {
                name = scrubName(name);
                dob = scrubDOB(dob);
            }
            
            const card = document.createElement('div');
            card.className = `appt-item ${appt.reason.toLowerCase().includes('chest') ? 'emergency-appt' : ''}`;
            card.innerHTML = `
                <div class="appt-meta">
                    <span class="appt-name">${name}</span>
                    <span class="appt-time">${appt.appointment_time}</span>
                </div>
                <div class="appt-doc"><i data-lucide="user-round" style="width:12px;height:12px;display:inline-block;margin-right:2px;"></i> ${appt.doctor_name}</div>
                <div class="appt-reason">"${appt.reason}"</div>
            `;
            appointmentsList.appendChild(card);
        });
        
        lucide.createIcons();
    } catch(err) {
        console.error("Error fetching appointments:", err);
    }
}

// GDPR Anonymizers
function scrubName(name) {
    const parts = name.split(' ');
    return parts.map(p => p.charAt(0) + '*'.repeat(Math.max(0, p.length - 1))).join(' ');
}

function scrubDOB(dob) {
    // Scrub dates like 12/04/1990 to **/**/1990
    return dob.replace(/^\d{2}\/\d{2}/, '**/**');
}

// Fetch Observability Telemetry Metrics
async function fetchTelemetry() {
    try {
        const response = await fetch(`${BASE_URL}/api/telemetry?_=${Date.now()}`);
        const tel = await response.json();
        
        const logs = tel.logs;
        const summary = tel.summary;
        
        if (logs.length > 0) {
            const latest = logs[0];
            const lat = latest.latency;
            
            // Set values in UI
            triageVal.innerText = `${latest.is_emergency ? '0.0' : lat.triage.toFixed(1)} ms`;
            ragVal.innerText = `${lat.rag.toFixed(1)} ms`;
            llmVal.innerText = `${lat.llm.toFixed(1)} ms`;
            ttsVal.innerText = `${lat.tts.toFixed(1)} ms`;
            
            const totalSec = (lat.total / 1000).toFixed(2);
            totalVal.innerText = `${totalSec}s`;
            
            // Adjust progress bars widths (scale relative to ceilings)
            pbTriage.style.width = `${Math.min(100, (lat.triage / 100) * 100)}%`;
            pbRag.style.width = `${Math.min(100, (lat.rag / 500) * 100)}%`;
            pbLlm.style.width = `${Math.min(100, (lat.llm / 2500) * 100)}%`;
            pbTts.style.width = `${Math.min(100, (lat.tts / 2500) * 100)}%`;
            pbTotal.style.width = `${Math.min(100, (lat.total / 4000) * 100)}%`;
            
            // Render logs list
            logStream.innerHTML = '';
            logs.forEach(log => {
                const item = document.createElement('div');
                item.className = `log-entry ${log.is_emergency ? 'log-alert' : 'log-info'}`;
                
                // Scrub logging if checkbox active
                let inputTxt = log.input;
                if (piiToggle.checked) {
                    // Simple replacement of potential patient booking patterns
                    inputTxt = inputTxt.replace(/(?:my name is|i am|this is)\s+([a-zA-Z\s]+)/i, "$1 [PII SCRUBBED]");
                }
                
                item.innerHTML = `
                    <span class="log-time">[${log.timestamp}]</span>
                    <span class="log-msg">In: "${inputTxt.slice(0, 30)}..." | RTT: ${log.latency.total.toFixed(0)}ms | Tokens: ${log.tokens}</span>
                `;
                logStream.appendChild(item);
            });
        }
    } catch(err) {
        console.error("Error fetching telemetry:", err);
    }
}

// Add Conversation log bubbles
function addMessage(sender, text) {
    const msg = document.createElement('div');
    msg.className = `message ${sender}-message`;
    
    const icon = sender === 'patient' ? 'user' : 'bot';
    const colorClass = sender === 'patient' ? 'text-secondary' : 'text-primary';
    
    msg.innerHTML = `
        <i data-lucide="${icon}" class="msg-icon ${colorClass}"></i>
        <div class="msg-content">
            <p>${text}</p>
        </div>
    `;
    transcriptBody.appendChild(msg);
    transcriptBody.scrollTop = transcriptBody.scrollHeight;
    
    lucide.createIcons();
}

// Add system notifications in log
function addSystemMessage(text) {
    const msg = document.createElement('div');
    msg.className = 'message system-message';
    msg.innerHTML = `
        <i data-lucide="info" class="msg-icon"></i>
        <div class="msg-content">
            <p>${text}</p>
        </div>
    `;
    transcriptBody.appendChild(msg);
    transcriptBody.scrollTop = transcriptBody.scrollHeight;
    
    lucide.createIcons();
}

// Text input submit helper
function submitTextQuery() {
    const text = chatInput.value.trim();
    if (text) {
        addMessage('patient', text);
        sendQueryToAgent(text);
        chatInput.value = '';
    }
}

// Event Listeners
sendBtn.addEventListener('click', submitTextQuery);
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        submitTextQuery();
    }
});

micBtn.addEventListener('click', () => {
    if (!recognition) {
        initSpeechRecognition();
    }
    
    if (isRecording) {
        isVoiceSession = false;
        recognition.stop();
    } else if (recognition) {
        recognition.start();
    }
});

// Setup click shortcut simulator chips
document.querySelectorAll('.shortcut-chip').forEach(chip => {
    chip.addEventListener('click', () => {
        const query = chip.getAttribute('data-query');
        addMessage('patient', query);
        sendQueryToAgent(query);
    });
});

clearLogBtn.addEventListener('click', () => {
    transcriptBody.innerHTML = '';
    addSystemMessage("Log cleared.");
});

// System database resets
resetDbBtn.addEventListener('click', async () => {
    try {
        const response = await fetch(`${BASE_URL}/api/reset?_=${Date.now()}`);
        if (response.ok) {
            addSystemMessage("Clinic database reset successfully.");
            fetchAppointments();
            fetchTelemetry();
        }
    } catch (e) {
        console.error(e);
    }
});

// Refresh appointments on PII toggle change
piiToggle.addEventListener('change', () => {
    fetchAppointments();
    fetchTelemetry();
});

// Initialize Lucide Vector Icons
lucide.createIcons();

// Initial seed loading
fetchAppointments();
fetchTelemetry();
setAgentState('idle');
