<div align="center">

```text
	    ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
	    ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
	    ██║███████║██████╔╝██║   ██║██║███████╗
	    ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
   ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
    ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
```

**A JARVIS-style voice assistant for Windows**

![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-blue?logo=windows)
![Python](https://img.shields.io/badge/Python-3.10+-green?logo=python)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange?logo=google)
![License](https://img.shields.io/badge/License-MIT-purple)

</div>

---

## What is this?

JARVIS is a voice-controlled assistant for Windows, inspired by the AI from Iron Man.

It listens for supported wake words, recognizes speech locally, and uses Google Gemini for AI responses. It can open websites, speak responses aloud, and perform supported Windows system actions.

**Important:** Speech recognition runs locally, but Gemini requests require an internet connection and are sent to Google's API.

---

## Features

- 🎙️ **Wake-word detection** — Activate the assistant using supported wake words.
- 🧠 **Offline speech recognition** — Vosk processes speech locally without cloud speech-to-text.
- 🔊 **Speech output** — Uses `pyttsx3` to speak responses aloud.
- 🤖 **AI fallback** — Google Gemini handles supported AI requests.
- 💻 **Windows system commands** — Supports configured actions such as locking, sleeping, shutting down, and restarting.
- 🌐 **Web actions** — Opens supported websites and URLs.
- 🔒 **Local speech recognition** — Audio recognition is handled locally; Gemini requests require internet access.

Available commands depend on the current implementation in `jarvis.py`.

---

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer
- A working microphone and speakers
- Internet connection for Gemini AI requests
- A Google Gemini API key

---

## Quick Install

### 1. Download the Windows branch

Clone the Windows version of the repository:

```powershell
git clone https://github.com/KTT-atest/Jarvis-Assistant-Windows-Fork.git
cd Jarvis-Assistant-Windows-Fork
```

### 2. Install Python

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/).

During installation, enable **Add Python to PATH** if the installer offers that option.

### 3. Run the Windows installer

Open PowerShell in the project folder:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_jarvis_windows.ps1
```

The installer will:

1. Check for an available Python installation.
2. Create a project-specific Python virtual environment.
3. Install the required Python packages.
4. Download and extract the Vosk speech recognition model.
5. Ask for your Gemini API key and save it as a Windows user environment variable.
6. Display the command to launch JARVIS.

The installer prepares the environment. It does not automatically launch JARVIS or configure Windows startup.

### 4. Launch JARVIS

Use the command printed by the installer. It should resemble:

```powershell
.\.venv\Scripts\python.exe .\jarvis.py
```

Keep the terminal open while using JARVIS.

---

## Requirements and API Configuration

### Google Gemini API Key

Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).

The installer asks for your key and saves it in the Windows user environment variable:

```text
GEMINI_API_KEY
```

The assistant reads the key from this environment variable when it starts. You should not need to hardcode your API key in `jarvis.py`.

If you change your API key, update the environment variable and start a new terminal or application process.

Availability, quotas, and pricing depend on Google's current policies.

### Vosk Speech Recognition Model

The installer downloads the English Vosk model:

```text
vosk-model-small-en-us-0.15
```

The model is stored outside the Git repository in your Windows user folder by default.

The default model path is:

```text
%USERPROFILE%\vosk-model\vosk-model-small-en-us-0.15
```

The model location can be overridden using the `VOSK_MODEL_PATH` environment variable.

### Gemini Model

The configured Gemini model defaults to:

```text
gemini-2.5-flash
```

The model can be overridden using the `GEMINI_MODEL` environment variable, provided the selected model is available to your API key.

---

## Voice Commands

JARVIS supports configured voice commands for Windows system actions, web actions, and AI requests.

### System Commands

Examples of supported system actions include:

| Command | Action |
|---|---|
| JARVIS, shutdown | Requests a system shutdown |
| JARVIS, restart | Requests a system restart |
| JARVIS, sleep | Requests system sleep |
| JARVIS, lock | Locks the Windows session |

Shutdown and restart actions may interrupt your work. Confirm any requested action before allowing it to execute.

### Applications and Web

JARVIS can open supported websites and URLs.

Examples of AI requests include:

- "JARVIS, what is the capital of Japan?"
- "JARVIS, explain quantum computing."
- "JARVIS, tell me a joke."

Exact commands and responses depend on the current implementation in `jarvis.py`.

---

## Configuration

Edit `jarvis.py` to customize JARVIS.

### Change the Wake Words

The default wake words are configured in the source code:

```python
WAKE_WORDS = ["jarvis", "friday"]
```

You can change them to other words supported by the speech recognition model.

### Gemini Configuration

The assistant reads its API key and model from environment variables:

```python
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
```

Do not hardcode your API key in the source code.

### Vosk Model Path

The default model path is:

```python
VOSK_MODEL_PATH = Path(os.environ.get(
    "VOSK_MODEL_PATH",
    str(Path.home() / "vosk-model" / "vosk-model-small-en-us-0.15")
))
```

This allows you to use a different Vosk model directory if needed.

---

## Project Structure

```text
Jarvis-Assistant/
├── jarvis.py
├── install_jarvis_windows.ps1
└── README.md
```

The installer creates the `.venv` directory and downloads the Vosk model separately.

The virtual environment and downloaded model should not be committed to GitHub.

---

## Security

- Never commit your Gemini API key to GitHub.
- Keep API keys in environment variables or another secure configuration method.
- Do not run untrusted commands suggested by an AI assistant without reviewing them.
- Shutdown and restart actions can interrupt your work.

---

## Credits

| Component | Source |
|---|---|
| Speech recognition | [Vosk](https://alphacephei.com/vosk) by Alpha Cephei |
| Speech output | [pyttsx3](https://github.com/nateshmbhat/pyttsx3) |
| AI fallback | [Google Gemini API](https://aistudio.google.com) |

---

## License

This project is licensed under the MIT License. See the repository's license file for details.

---

<div align="center">

*"Shall I activate the suit, sir?"*

</div>
