import sounddevice as sd
import queue, json, subprocess, os, socket, sys
from pathlib import Path

# Force IPv4
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(host, port, family=0, *a, **kw):
    return _orig_getaddrinfo(host, port, socket.AF_INET, *a, **kw)
socket.getaddrinfo = _ipv4_only

from vosk import Model, KaldiRecognizer

WAKE_WORDS     = ["jarvis", "jonas", "davis", "travis", "friday"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_KEY_HERE")
GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

VOSK_MODEL_PATH = Path(os.environ.get(
    "VOSK_MODEL_PATH",
    str(Path.home() / "vosk-model" / "vosk-model-small-en-us-0.15")
))

PIPER_MODEL = Path(os.environ.get(
    "PIPER_MODEL_PATH",
    str(Path.home() / "piper-voices" / "jarvis-high.onnx")
))

# Check if piper is available
PIPER_AVAILABLE = subprocess.run(
    ["piper", "--help"], capture_output=True
).returncode == 0 if os.name != 'nt' else subprocess.run(
    ["piper.exe", "--help"], capture_output=True
).returncode == 0

model = Model(str(VOSK_MODEL_PATH))
rec   = KaldiRecognizer(model, 16000)
q     = queue.Queue()
is_speaking  = False
conversation = []

COMMANDS = {
    "shutdown":      "shutdown /s /t 0",
    "shut down":     "shutdown /s /t 0",
    "reboot":        "shutdown /r /t 0",
    "restart":       "shutdown /r /t 0",
    "sleep":         "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
    "lock":          "rundll32.exe user32.dll,LockWorkStation",
    "lock screen":   "rundll32.exe user32.dll,LockWorkStation",
    "volume up":     "powershell -c \"$vol = [Math]::Min(100, (Get-AudioDevice -PlaybackVolume) + 10); Set-AudioDevice -PlaybackVolume $vol\"",
    "volume down":   "powershell -c \"$vol = [Math]::Max(0, (Get-AudioDevice -PlaybackVolume) - 10); Set-AudioDevice -PlaybackVolume $vol\"",
    "open browser":  "start https://google.com",
    "open terminal": "start cmd",
    "open gmail":    "start https://mail.google.com",
    "compose email": "start https://mail.google.com/mail/?view=cm&fs=1",
}

CONTACTS = {
    # "john": "john@example.com",
}

GEMINI_SYSTEM = """You are JARVIS, Tony Stark's AI assistant running on a Windows PC.
You are calm, professional and intelligent. Occasional dry wit is acceptable but keep it rare and subtle.
Prioritize being helpful, accurate and concise over being funny.
You have full awareness of the user's system via the context injected with each message.
When given a voice command, respond ONLY with a valid JSON object — no markdown, no extra text, no code fences.

JSON format:
{
  "action": "speak" | "run" | "open_url" | "run_and_speak",
  "value": "command or url (empty string if action is speak)",
  "speech": "what JARVIS says out loud — always 1 sentence, professional and concise"
}

Action types:
- "speak": just say something
- "run": run a Windows command silently
- "open_url": open a URL in the browser
- "run_and_speak": run command and speak its output

Examples:
"check system health" -> {"action":"run_and_speak","value":"powershell -c \"Get-WmiObject Win32_Processor | Select LoadPercentage | Format-List\"","speech":"Running diagnostics, sir."}
"what time is it" -> {"action":"run_and_speak","value":"powershell -c \"Get-Date -Format 'HH:mm'\"","speech":"Checking the time, sir."}
"open youtube" -> {"action":"open_url","value":"https://youtube.com","speech":"Opening YouTube, sir."}
"capital of france" -> {"action":"speak","value":"","speech":"Paris, sir."}"""


def get_system_context():
    try:
        cpu  = subprocess.check_output(
            'powershell -c "(Get-WmiObject Win32_Processor).LoadPercentage"',
            shell=True).decode().strip()
        ram  = subprocess.check_output(
            'powershell -c "$os = Get-WmiObject Win32_OperatingSystem; [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB, 1)"',
            shell=True).decode().strip()
        disk = subprocess.check_output(
            'powershell -c "Get-PSDrive C | Select-Object @{N=\'Free\';E={[math]::Round($_.Free/1GB,1)}} | Format-List"',
            shell=True).decode().strip()
        batt = subprocess.check_output(
            'powershell -c "(Get-WmiObject Win32_Battery).EstimatedChargeRemaining"',
            shell=True).decode().strip() or "N/A"
        return f"CPU: {cpu}% | RAM used: {ram}GB | Disk: {disk} | Battery: {batt}%"
    except Exception as e:
        return f"System context unavailable: {e}"


def speak(text):
    global is_speaking
    is_speaking = True
    print(f"JARVIS: {text}")
    clean = text.replace('"', '').replace("'", '').replace('`', '').strip()
    q.queue.clear()

    if PIPER_AVAILABLE and PIPER_MODEL.exists():
        try:
            tmp = Path(os.environ.get("TEMP", "C:/Temp")) / "jarvis_tts.wav"
            piper_exe = "piper.exe" if os.name == 'nt' else "piper"
            subprocess.run(
                f'echo {clean} | {piper_exe} --model "{PIPER_MODEL}" --output_file "{tmp}"',
                shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                f'powershell -c "(New-Object Media.SoundPlayer \'{tmp}\').PlaySync()"',
                shell=True
            )
        except Exception as e:
            print(f"Piper error: {e}, falling back to pyttsx3")
            _speak_pyttsx3(clean)
    else:
        _speak_pyttsx3(clean)

    q.queue.clear()
    is_speaking = False


def _speak_pyttsx3(text):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        voices = engine.getProperty('voices')
        # Try to find a British male voice
        for v in voices:
            if 'male' in v.name.lower() or 'david' in v.name.lower():
                engine.setProperty('voice', v.id)
                break
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"pyttsx3 error: {e}")


def ask_gemini(prompt):
    import requests, json as _json
    global conversation
    context = get_system_context()
    full_prompt = f"[System context: {context}]\nUser command: {prompt}"
    messages = conversation[-6:]
    messages.append({"role": "user", "parts": [{"text": full_prompt}]})
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
            json={
                "contents": messages,
                "generationConfig": {"maxOutputTokens": 200},
                "systemInstruction": {"parts": [{"text": GEMINI_SYSTEM}]}
            },
            timeout=15
        )
        raw = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        raw = raw.strip().strip("```json").strip("```").strip()
        result = _json.loads(raw)
        print(f"Gemini action: {result}")
        conversation.append({"role": "user",  "parts": [{"text": full_prompt}]})
        conversation.append({"role": "model", "parts": [{"text": raw}]})
        if len(conversation) > 12:
            conversation = conversation[-12:]
        return result
    except Exception as e:
        print(f"Gemini error: {e}")
        return {"action": "speak", "value": "", "speech": "Reasoning systems unavailable, sir."}


def handle_email(command_text):
    if any(w in command_text for w in ["compose email", "new email", "write email"]):
        subprocess.Popen("start https://mail.google.com/mail/?view=cm&fs=1", shell=True)
        speak("Opening compose window, sir.")
        return True
    if "email" in command_text:
        for name, address in CONTACTS.items():
            if name in command_text:
                subprocess.Popen(f"start https://mail.google.com/mail/?view=cm&fs=1&to={address}", shell=True)
                speak(f"Composing email to {name}, sir.")
                return True
        subprocess.Popen("start https://mail.google.com/mail/?view=cm&fs=1", shell=True)
        speak("Opening compose window, sir.")
        return True
    return False


def execute(result):
    action = result.get("action", "speak")
    value  = result.get("value", "")
    speech = result.get("speech", "Done, sir.")
    if action == "speak":
        speak(speech)
    elif action == "run":
        speak(speech)
        subprocess.Popen(value, shell=True)
    elif action == "open_url":
        speak(speech)
        subprocess.Popen(f"start {value}", shell=True)
    elif action == "run_and_speak":
        speak(speech)
        try:
            output = subprocess.check_output(value, shell=True, timeout=10).decode().strip()
            print(f"Output: {output}")
            speak(output)
        except Exception as e:
            speak("Command execution failed, sir.")


def handle(text):
    global is_speaking
    if is_speaking:
        return
    text = text.lower().strip()
    print(f"Heard: {text}")
    wake_found = any(w in text for w in WAKE_WORDS)
    if not wake_found:
        return
    command_text = text
    for w in WAKE_WORDS:
        command_text = command_text.replace(w, "").strip(" ,.")
    if not command_text:
        speak("Yes, sir?")
        return
    for keyword, action in COMMANDS.items():
        if keyword in command_text:
            subprocess.Popen(action, shell=True)
            speak("Done, sir.")
            return
    if handle_email(command_text):
        return
    print(f"Asking Gemini: {command_text}")
    speak("One moment.")
    result = ask_gemini(command_text)
    execute(result)


def callback(indata, frames, time, status):
    if not is_speaking:
        q.put(bytes(indata))


print("J.A.R.V.I.S. online.")
speak("All systems online. How can I assist you, sir?")

with sd.RawInputStream(samplerate=16000, blocksize=8000,
                        dtype="int16", channels=1, callback=callback):
    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "")
            if text:
                handle(text)
