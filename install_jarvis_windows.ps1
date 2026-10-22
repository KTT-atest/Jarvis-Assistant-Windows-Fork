$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ProjectDir = $PSScriptRoot
$VenvDir = Join-Path $ProjectDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

$ModelsDir = Join-Path $ProjectDir "models"
$PiperDir = Join-Path $ModelsDir "piper"
$VoskDir = Join-Path $ModelsDir "vosk"
$VoskModelName = "vosk-model-small-en-us-0.15"
$VoskModelDir = Join-Path $VoskDir $VoskModelName

$PiperModelName = "jarvis-high.onnx"
$PiperModelPath = Join-Path $PiperDir $PiperModelName
$PiperConfigPath = "$PiperModelPath.json"

$PiperModelUrl = "https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/high/jarvis-high.onnx"
$PiperConfigUrl = "https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/high/jarvis-high.onnx.json"

$VoskZipPath = Join-Path $ModelsDir "$VoskModelName.zip"
$VoskUrl = "https://alphacephei.com/vosk/models/$VoskModelName.zip"

function Write-Step {
param([string]$Message)
Write-Host ""
Write-Host "==> $Message" -ForegroundColor Cyan
}

function Download-File {
param(
[Parameter(Mandatory = $true)][string]$Url,
[Parameter(Mandatory = $true)][string]$Destination,
[int64]$MinimumBytes = 1
)

if ((Test-Path $Destination) -and
    (Get-Item $Destination).Length -ge $MinimumBytes) {
    Write-Host "Already downloaded: $Destination" -ForegroundColor DarkGray
    return
}

$TempPath = "$Destination.download"
Remove-Item $TempPath -Force -ErrorAction SilentlyContinue

Write-Host "Downloading $([System.IO.Path]::GetFileName($Destination)) ..."
try {
    Invoke-WebRequest -Uri $Url -OutFile $TempPath -UseBasicParsing

    if (-not (Test-Path $TempPath)) {
        throw "The download did not create a file."
    }

    if ((Get-Item $TempPath).Length -lt $MinimumBytes) {
        throw "The downloaded file is unexpectedly small."
    }

    Move-Item $TempPath $Destination -Force
}
catch {
    Remove-Item $TempPath -Force -ErrorAction SilentlyContinue
    throw "Download failed: $Url`n$($_.Exception.Message)"
}

}

try {
Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "       JARVIS Windows Installer"
Write-Host "======================================" -ForegroundColor Green

# Check that Python is installed.
Write-Step "Checking Python"

$PythonCommand = Get-Command py -ErrorAction SilentlyContinue
if ($PythonCommand) {
    & py -3.11 --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        $PythonLauncherArgs = @("-3.11")
    }
    else {
        & py -3.10 --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PythonLauncherArgs = @("-3.10")
        }
        else {
            & py -3 --version
            if ($LASTEXITCODE -ne 0) {
                throw "Python 3.10 or newer is required. Install Python from https://www.python.org/downloads/windows/"
            }
            $PythonLauncherArgs = @("-3")
        }
    }
    $PythonCommandLine = "py"
}
else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        throw "Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/windows/ and enable Python in PATH."
    }

    & python --version
    if ($LASTEXITCODE -ne 0) {
        throw "Python could not be started."
    }

    $PythonCommandLine = "python"
    $PythonLauncherArgs = @()
}

# Create the virtual environment if necessary.
Write-Step "Creating Python virtual environment"

if (-not (Test-Path $PythonExe)) {
    if ($PythonCommandLine -eq "py") {
        & py @PythonLauncherArgs -m venv $VenvDir
    }
    else {
        & python -m venv $VenvDir
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the Python virtual environment."
    }
}
else {
    Write-Host "Existing virtual environment found."
}

if (-not (Test-Path $PythonExe)) {
    throw "Virtual environment Python executable was not created."
}

# Install the project dependencies.
Write-Step "Installing Python dependencies"

& $PythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip."
}

& $PythonExe -m pip install requests sounddevice vosk piper-tts
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install Python dependencies."
}

# Create directories for models.
Write-Step "Preparing model directories"

New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
New-Item -ItemType Directory -Force -Path $PiperDir | Out-Null
New-Item -ItemType Directory -Force -Path $VoskDir | Out-Null

# Download the JARVIS Piper voice.
Write-Step "Downloading the JARVIS Piper voice"

Download-File `
    -Url $PiperModelUrl `
    -Destination $PiperModelPath `
    -MinimumBytes 1000000

Download-File `
    -Url $PiperConfigUrl `
    -Destination $PiperConfigPath `
    -MinimumBytes 100

# Validate the model configuration JSON.
Write-Step "Validating Piper configuration"

& $PythonExe -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8'))" $PiperConfigPath
if ($LASTEXITCODE -ne 0) {
    throw "The Piper JSON configuration is invalid."
}

# Download and extract the Vosk speech-recognition model.
Write-Step "Installing the Vosk speech-recognition model"

if (-not (Test-Path (Join-Path $VoskModelDir "am"))) {
    Download-File `
        -Url $VoskUrl `
        -Destination $VoskZipPath `
        -MinimumBytes 1000000

    Expand-Archive -Path $VoskZipPath -DestinationPath $VoskDir -Force

    if (-not (Test-Path (Join-Path $VoskModelDir "am"))) {
        throw "Vosk extraction did not produce the expected model directory."
    }
}
else {
    Write-Host "Vosk model already exists."
}

# Configure environment variables for the current Windows user.
Write-Step "Configuring model paths"

[Environment]::SetEnvironmentVariable(
    "PIPER_MODEL_PATH",
    $PiperModelPath,
    "User"
)

[Environment]::SetEnvironmentVariable(
    "VOSK_MODEL_PATH",
    $VoskModelDir,
    "User"
)

# Also set them for this PowerShell session.
$env:PIPER_MODEL_PATH = $PiperModelPath
$env:VOSK_MODEL_PATH = $VoskModelDir

# Ask for a Gemini API key only if one is not already configured.
Write-Step "Checking Gemini API configuration"

$ExistingApiKey = [Environment]::GetEnvironmentVariable(
    "GEMINI_API_KEY",
    "User"
)

if ([string]::IsNullOrWhiteSpace($ExistingApiKey)) {
    $SecureKey = Read-Host "Enter your Gemini API key (input is visible)" -AsSecureString
    $Bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)

    try {
        $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Bstr)
        if ([string]::IsNullOrWhiteSpace($ApiKey)) {
            throw "No API key was entered."
        }

        [Environment]::SetEnvironmentVariable(
            "GEMINI_API_KEY",
            $ApiKey,
            "User"
        )

        $env:GEMINI_API_KEY = $ApiKey
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr)
        $ApiKey = $null
        $SecureKey.Dispose()
    }
}
else {
    Write-Host "A user-level Gemini API key is already configured."
}

# Remove the downloaded Vosk archive after successful extraction.
Remove-Item $VoskZipPath -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "       Installation completed"
Write-Host "======================================" -ForegroundColor Green

Write-Host ""
Write-Host "Piper voice: $PiperModelPath"
Write-Host "Vosk model:  $VoskModelDir"
Write-Host ""
Write-Host "Launch Jarvis using:"
Write-Host '  .\.venv\Scripts\python.exe .\jarvis.py' -ForegroundColor Yellow
Write-Host ""
Write-Host "Note: jarvis.py must use Piper for speech output to use this voice."

}
catch {
Write-Host ""
Write-Host "INSTALLATION FAILED" -ForegroundColor Red
Write-Host $_.Exception.Message -ForegroundColor Red
exit 1
}
