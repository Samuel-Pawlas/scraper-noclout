# Noclout Scraper - Automated Run Script
# Designed for Windows Task Scheduler
# Runs daily at midnight
# Can also be run manually: .\run_automated.ps1

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) {
    $ScriptDir = $PSScriptRoot
}
if (-not $ScriptDir) {
    $ScriptDir = "C:\Finds\Scrapers\scraper-noclout"
}

$LogFile = Join-Path $ScriptDir "scraper_log_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
$ErrorLog = Join-Path $ScriptDir "scraper_errors.log"

# Try multiple Python paths for reliability
$PythonPaths = @(
    "$env:USERPROFILE\AppData\Local\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "C:\Users\samip\AppData\Local\Programs\Python\Python312\python.exe",
    "python.exe",
    "py.exe"
)

$PythonPath = $null
foreach ($Path in $PythonPaths) {
    if (Test-Path $Path) {
        $PythonPath = $Path
        break
    }
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$Level] $Message"
    Write-Host $LogMessage
    Add-Content -Path $LogFile -Value $LogMessage -Encoding UTF8 -ErrorAction SilentlyContinue
}

function Write-Error-Log {
    param([string]$Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [ERROR] $Message"
    Add-Content -Path $ErrorLog -Value $LogMessage -Encoding UTF8 -ErrorAction SilentlyContinue
}

function Test-Python {
    if (-not $PythonPath) {
        Write-Log "Python not found at any of the expected paths" "ERROR"
        return $false
    }
    
    try {
        $Version = & $PythonPath --version 2>&1
        Write-Log "Python found: $Version at $PythonPath"
        return $true
    }
    catch {
        Write-Log "Failed to run Python: $_" "ERROR"
        return $false
    }
}

function Install-Dependencies {
    Write-Log "Checking/Installing dependencies..."
    
    $RequiredPackages = @("requests", "beautifulsoup4", "lxml", "supabase", "Pillow", "numpy", "torch", "torchvision", "transformers")
    $MissingPackages = @()
    
    try {
        $InstalledPackages = & $PythonPath -m pip list 2>&1 | Out-String
        
        foreach ($Package in $RequiredPackages) {
            if ($InstalledPackages -notmatch [regex]::Escape($Package)) {
                $MissingPackages += $Package
            }
        }
        
        if ($MissingPackages.Count -gt 0) {
            Write-Log "Missing packages: $($MissingPackages -join ', ')"
            Write-Log "Installing missing packages..."
            
            $Result = & $PythonPath -m pip install $MissingPackages --quiet --upgrade 2>&1
            if ($LASTEXITCODE -ne 0) {
                Write-Log "pip install failed, trying with --user" "WARNING"
                $Result = & $PythonPath -m pip install $MissingPackages --user --quiet --upgrade 2>&1
            }
            
            Write-Log "Dependencies installed"
        }
        else {
            Write-Log "All dependencies already installed"
        }
        
        return $true
    }
    catch {
        Write-Log "Error checking/installing dependencies: $_" "ERROR"
        Write-Error-Log "Dependency error: $_"
        return $false
    }
}

function Invoke-Scraper {
    Write-Log "Starting Noclout Scraper..."
    Write-Log "Script directory: $ScriptDir"
    Write-Log "Scraper file: $ScriptDir\scraper.py"
    
    if (-not (Test-Path "$ScriptDir\scraper.py")) {
        Write-Log "scraper.py not found in $ScriptDir" "ERROR"
        return $false
    }
    
    try {
        $Env:PYTHONPATH = $ScriptDir
        
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
            Write-Error-Log "Scraper failed with exit code $($Process.ExitCode)"
            return $false
        }
    }
    catch {
        Write-Log "Error running scraper: $_" "ERROR"
        Write-Error-Log "Scraper execution error: $_"
        return $false
    }
}

# Main execution
Write-Log "============================================================" "INFO"
Write-Log "Noclout Scraper - Automated Run" "INFO"
Write-Log "============================================================" "INFO"
Write-Log "Started at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" "INFO"

$Success = $false

if (Test-Python) {
    if (Install-Dependencies) {
        $Success = Invoke-Scraper
    }
}

Write-Log "Finished at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" "INFO"

if ($Success) {
    Write-Log "Automation completed successfully" "INFO"
    exit 0
}
else {
    Write-Log "Automation failed - check logs for details" "ERROR"
    exit 1
}
