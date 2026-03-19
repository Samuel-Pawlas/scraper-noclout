# Noclout Scraper - Automated Run Script
# Designed for Windows Task Scheduler
# Runs daily at midnight

param(
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) {
    $ScriptDir = $PSScriptRoot
}
if (-not $ScriptDir) {
    $ScriptDir = "C:\Finds\Scrapers\scraper-noclout"
}

$LogFile = Join-Path $ScriptDir "scraper_log_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
$PythonPath = "$env:USERPROFILE\AppData\Local\Programs\Python\Python312\python.exe"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$Level] $Message"
    Write-Host $LogMessage
    Add-Content -Path $LogFile -Value $LogMessage -Encoding UTF8
}

function Install-Dependencies {
    Write-Log "Installing dependencies..."
    try {
        & $PythonPath -m pip install -r "$ScriptDir\requirements.txt" --quiet
        if ($LASTEXITCODE -ne 0) {
            throw "pip install failed"
        }
        Write-Log "Dependencies installed successfully"
        return $true
    }
    catch {
        Write-Log "Failed to install dependencies: $_" "ERROR"
        return $false
    }
}

function Test-Python {
    if (-not (Test-Path $PythonPath)) {
        Write-Log "Python not found at $PythonPath" "ERROR"
        return $false
    }
    
    try {
        $Version = & $PythonPath --version 2>&1
        Write-Log "Python version: $Version"
        return $true
    }
    catch {
        Write-Log "Failed to run Python: $_" "ERROR"
        return $false
    }
}

function Invoke-Scraper {
    Write-Log "Starting Noclout Scraper..."
    Write-Log "Script directory: $ScriptDir"
    
    try {
        $Process = Start-Process -FilePath $PythonPath `
            -ArgumentList "$ScriptDir\scraper.py" `
            -WorkingDirectory $ScriptDir `
            -NoNewWindow `
            -Wait `
            -PassThru
        
        if ($Process.ExitCode -eq 0) {
            Write-Log "Scraper completed successfully"
            return $true
        }
        else {
            Write-Log "Scraper failed with exit code $($Process.ExitCode)" "ERROR"
            return $false
        }
    }
    catch {
        Write-Log "Error running scraper: $_" "ERROR"
        return $false
    }
}

# Main execution
Write-Log "=" * 60
Write-Log "Noclout Scraper - Automated Run"
Write-Log "=" * 60

if (-not (Test-Python)) {
    exit 1
}

if (-not (Install-Dependencies)) {
    exit 1
}

if (Invoke-Scraper) {
    Write-Log "Automation completed successfully"
    exit 0
}
else {
    Write-Log "Automation failed" "ERROR"
    exit 1
}
