"""
J.A.R.V.I.S. — Windows edition
Requirements:
    pip install sounddevice vosk requests pyttsx3
Also download a Vosk English model and set VOSK_MODEL_PATH to its folder.
Set GEMINI_API_KEY in your environment before starting.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote

import sounddevice as sd
import pyttsx3
import requests
from vosk import Model, KaldiRecognizer

# ---------- Configuration ----------
WAKE_WORDS = ["jarvis", "friday"]
BASE_DIR = Path(__file__).resolve().parent
VOSK_MODEL_PATH = Path(os.environ.get(
    "VOSK_MODEL_PATH",
    str(Path.home() / "vosk-model" / "vosk-model-small-en-us-0.15")
))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
SAMPLE_RATE = 16000

CONTACTS = {
    # "john": "john@example.com",
    # "mom": "mom@example.com",
}

COMMANDS = {
    "shutdown": ["shutdown", "/s", "/t", "0"],
    "shut down": ["shutdown", "/s", "/t", "0"],
    "reboot": ["shutdown", "/r", "/t", "0"],
    "restart": ["shutdown", "/r", "/t", "0"],
    "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
    "lock screen": ["rundll32.exe", "user32.dll,LockWorkStation"],
    "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
}

GEMINI_SYSTEM = """You are JARVIS, a capable Windows voice assistant.
Be calm, professional, concise, and accurate.
You receive system context with each user command.
Respond ONLY with one valid JSON object, no markdown or code fences:
{"action":"speak|run|open_url|run_and_speak","value":"PowerShell command or URL","speech":"one concise sentence"}

Actions:
- speak: answer verbally, no command.
- run: execute a PowerShell command.
- open_url: open a URL in the default browser.
- run_and_speak: execute a PowerShell command and speak its output.

Use PowerShell syntax, not Bash/Linux commands.
Examples:
"check system health" -> {"action":"run_and_speak","value":"$cpu = (Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average; $os = Get-CimInstance Win32_OperatingSystem; 'CPU: ' + $cpu + '% | RAM free: ' + [math]::Round($os.FreePhysicalMemory/1MB,1) + ' GB'","speech":"Checking system health, sir."}
"what time is it" -> {"action":"run_and_speak","value":"Get-Date -Format 'HH:mm'","speech":"Checking the time, sir."}
"open youtube" -> {"action":"open_url","value":"https://youtube.com","speech":"Opening YouTube, sir."}
"what is my battery" -> {"action":"speak","value":"","speech":"Your battery details are in the system context."}
Do not generate commands that delete files, change security settings, or perform irreversible actions without asking first.
"""

audio_queue = queue.Queue()
is_speaking = False
conversation = []
speech_lock = threading.Lock()
tts_engine = pyttsx3.init()
tts_engine.setProperty("rate", 180)


def speak(text):
    global is_speaking
    text = str(text or "").strip()
    if not text:
        return
    with speech_lock:
        is_speaking = True
        try:
            print(f"JARVIS: {text}")
            tts_engine.say(text)
            tts_engine.runAndWait()
        except Exception as exc:
            print(f"TTS error: {exc}")
        finally:
            is_speaking = False
            # Remove queued microphone audio captured while speaking.
            while not audio_queue.empty():
                try:
                    audio_queue.get_nowait()
                except queue.Empty:
                    break


def get_system_context():
    """Collect Windows system details with PowerShell; tolerate unavailable fields."""
    ps = r"""
$ErrorActionPreference = 'SilentlyContinue'
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
$os = Get-CimInstance Win32_OperatingSystem
$ramTotal = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$ramFree = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$ramUsed = [math]::Round($ramTotal - $ramFree, 1)
$drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$env:SystemDrive'"
$diskFree = [math]::Round($drive.FreeSpace / 1GB, 1)
$diskTotal = [math]::Round($drive.Size / 1GB, 1)
$uptime = (Get-Date) - $os.LastBootUpTime
$battery = Get-CimInstance Win32_Battery
if ($battery) { $batt = "$($battery.EstimatedChargeRemaining)%"; $battStatus = $battery.BatteryStatus } else { $batt = 'N/A'; $battStatus = 'N/A' }
$topCpu = (Get-Process | Sort-Object CPU -Descending | Select-Object -First 3 -ExpandProperty ProcessName) -join ', '
$topMem = (Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 3 -ExpandProperty ProcessName) -join ', '
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*'} | Select-Object -First 1 -ExpandProperty IPAddress
"CPU: $cpu% | RAM: $ramUsed/$ramTotal GB | Disk: $diskFree GB free of $diskTotal GB | Battery: $batt ($battStatus) | Uptime: $($uptime.Days)d $($uptime.Hours)h | Top CPU: $topCpu | Top RAM: $topMem | IP: $ip"
"""
    try:
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            text=True, timeout=12, stderr=subprocess.DEVNULL
        ).strip()
    except Exception as exc:
        return f"System context unavailable: {exc}"


def ask_gemini(prompt):
    global conversation
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_KEY_HERE":
        return {"action": "speak", "value": "", "speech": "Please configure your Gemini API key first."}

    context = get_system_context()
    full_prompt = f"[System context: {context}]\nUser command: {prompt}"
    messages = conversation[-6:] + [{"role": "user", "parts": [{"text": full_prompt}]}]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_API_KEY}",
    try:
        response = requests.post(
            url,
            json={
                "contents": messages,
                "generationConfig": {"maxOutputTokens": 250, "responseMimeType": "application/json"},
                "systemInstruction": {"parts": [{"text": GEMINI_SYSTEM}]},
            },
            timeout=25,
        )
        response.raise_for_status()
        raw = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        result = json.loads(raw)
        if result.get("action") not in {"speak", "run", "open_url", "run_and_speak"}:
            raise ValueError("Gemini returned an unsupported action")
        conversation.extend([
            {"role": "user", "parts": [{"text": full_prompt}]},
            {"role": "model", "parts": [{"text": raw}]},
        ])
        conversation = conversation[-12:]
        return result
    except Exception as exc:
        print(f"Gemini error: {exc}")
        return {"action": "speak", "value": "", "speech": "My reasoning service is unavailable right now, sir."}


def open_url(url):
    if url:
        webbrowser.open(url)


def handle_email(command_text):
    if any(term in command_text for term in ("compose email", "new email", "write email")):
        open_url("https://mail.google.com/mail/?view=cm&fs=1")
        speak("Opening the email compose window, sir.")
        return True
    if "email" in command_text:
        for name, address in CONTACTS.items():
            if name in command_text:
                open_url("https://mail.google.com/mail/?view=cm&fs=1&to=" + quote(address))
                speak(f"Composing an email to {name}, sir.")
                return True
        open_url("https://mail.google.com/mail/?view=cm&fs=1")
        speak("Opening the email compose window, sir.")
        return True
    return False


def execute(result):
    action = result.get("action", "speak")
    value = str(result.get("value", "") or "")
    speech = str(result.get("speech", "Done, sir.") or "Done, sir.")

    if action == "speak":
        speak(speech)
    elif action == "open_url":
        speak(speech)
        open_url(value)
    elif action in {"run", "run_and_speak"}:
        speak(speech)
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", value],
                capture_output=True, text=True, timeout=15
            )
            output = (completed.stdout or completed.stderr).strip()
            if action == "run_and_speak" and output:
                print(f"Output: {output}")
                speak(output[:1200])
            elif completed.returncode:
                print(f"PowerShell returned exit code {completed.returncode}: {output}")
        except Exception as exc:
            print(f"Command error: {exc}")
            if action == "run_and_speak":
                speak("Command execution failed, sir.")


def handle(text):
    text = (text or "").lower().strip()
    if not text:
        return
    print(f"Heard: {text}")
    if not any(word in text for word in WAKE_WORDS):
        return
    command_text = text
    for word in WAKE_WORDS:
        command_text = command_text.replace(word, " ")
    command_text = " ".join(command_text.replace(",", " ").split()).strip(" .")
    if not command_text:
        speak("Yes, sir?")
        return

    # Local, predictable actions. Confirm destructive power actions.
    if command_text in {"shutdown", "shut down", "reboot", "restart"}:
        speak(f"Please say 'confirm {command_text}' to proceed.")
        pending_power_action["value"] = command_text
        pending_power_action["expires"] = time.time() + 10
        return
    if command_text.startswith("confirm "):
        requested = command_text.removeprefix("confirm ").strip()
        if time.time() <= pending_power_action["expires"] and requested == pending_power_action["value"]:
            cmd = COMMANDS.get(requested)
            if cmd:
                subprocess.Popen(cmd)
                pending_power_action["value"] = ""
                speak("Executing, sir.")
                return
        speak("That confirmation expired or did not match.")
        return

    for keyword, cmd in COMMANDS.items():
        if keyword in command_text:
            subprocess.Popen(cmd)
            speak("Done, sir.")
            return
    if "open browser" in command_text:
        open_url("https://google.com")
        speak("Opening your browser, sir.")
        return
    if "open gmail" in command_text:
        open_url("https://mail.google.com")
        speak("Opening Gmail, sir.")
        return
    if handle_email(command_text):
        return

    speak("One moment, sir.")
    execute(ask_gemini(command_text))


def audio_callback(indata, frames, callback_time, status):
    if status:
        print(f"Audio input status: {status}", file=sys.stderr)
    if not is_speaking:
        audio_queue.put(bytes(indata))


pending_power_action = {"value": "", "expires": 0}

def main():
    if not VOSK_MODEL_PATH.is_dir():
        print(f"Vosk model folder not found: {VOSK_MODEL_PATH}")
        print("Set VOSK_MODEL_PATH or download the Vosk English model.")
        sys.exit(1)
    print("Loading Vosk model...")
    model = Model(str(VOSK_MODEL_PATH))
    recognizer = KaldiRecognizer(model, SAMPLE_RATE)
    speak("JARVIS is online. How can I assist you, sir?")
    print("Listening. Say 'Jarvis' followed by a command.")
    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE, blocksize=8000, dtype="int16",
            channels=1, callback=audio_callback
        ):
            while True:
                data = audio_queue.get()
                if recognizer.AcceptWaveform(data):
                    recognized = json.loads(recognizer.Result()).get("text", "")
                    if recognized:
                        handle(recognized)
    except KeyboardInterrupt:
        print("\nJARVIS shutting down.")
    except Exception as exc:
        print(f"JARVIS stopped: {exc}")
        raise


if __name__ == "__main__":
    main()
