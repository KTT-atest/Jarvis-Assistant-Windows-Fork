# JARVIS Windows setup script
# Run from the folder containing jarvis.py in Windows PowerShell.
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectDir ".venv"
$ModelDir = Join-Path $ProjectDir "vosk-model-small-en-us-0.15"
$ModelZip = Join-Path $env:TEMP "vosk-model-small-en-us-0.15.zip"
$ModelUrl = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"

Write-Host "`n=== JARVIS Windows setup ===" -ForegroundColor Cyan

# Check Python
$Python = Get-Command py -ErrorAction SilentlyContinue
if ($Python) {
    $PythonCmd = "py"
    $PythonArgs = @("-3")
} else {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $Python) {
        Write-Host "Python 3.10+ is required. Install it from https://www.python.org/downloads/windows/"
        Write-Host "During installation, enable 'Add python.exe to PATH', then rerun this script."
        exit 1
    }
    $PythonCmd = "python"
    $PythonArgs = @()
}

# Create an isolated Python environment and install packages
if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating Python virtual environment..."
    & $PythonCmd @PythonArgs -m venv $VenvDir
}
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

Write-Host "Installing Python dependencies..."
& $VenvPython -m pip install --upgrade pip
& $VenvPip install sounddevice vosk requests pyttsx3

# Download and unpack Vosk speech recognition model
if (-not (Test-Path (Join-Path $ModelDir "am"))) {
    Write-Host "Downloading Vosk English speech-recognition model (~40 MB)..."
    Invoke-WebRequest -Uri $ModelUrl -OutFile $ModelZip
    Write-Host "Extracting Vosk model..."
    Expand-Archive -Path $ModelZip -DestinationPath $ProjectDir -Force
    Remove-Item $ModelZip -Force
}

# Set model path for this project/user
[Environment]::SetEnvironmentVariable("VOSK_MODEL_PATH", $ModelDir, "User")
$env:VOSK_MODEL_PATH = $ModelDir

# Ask for Gemini key, but don't overwrite an existing one
$ExistingKey = [Environment]::GetEnvironmentVariable("GEMINI_API_KEY", "User")
if (-not $ExistingKey) {
    $Key = Read-Host "Paste your Gemini API key (leave blank to configure later)"
    if ($Key) {
        [Environment]::SetEnvironmentVariable("GEMINI_API_KEY", $Key, "User")
        $env:GEMINI_API_KEY = $Key
    }
}

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host "To start JARVIS, run:"
Write-Host "  .\.venv\Scripts\python.exe .\jarvis.py"
Write-Host "`nIf microphone access is blocked, enable it in Windows Settings > Privacy & security > Microphone."
