# Noclout Scraper - Task Scheduler Setup
# Run this script once to set up daily automation at midnight
# Usage:
#   .\setup_scheduler.ps1        - Set up daily automation
#   .\setup_scheduler.ps1 -RunNow - Set up and run now
#   .\setup_scheduler.ps1 -Uninstall - Remove automation

param(
    [switch]$Uninstall,
    [switch]$RunNow
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) {
    $ScriptDir = $PSScriptRoot
}
if (-not $ScriptDir) {
    $ScriptDir = "C:\Finds\Scrapers\scraper-noclout"
}

$TaskName = "NocloutDailyScraper"
$AutomationScript = Join-Path $ScriptDir "run_automated.ps1"
$ManualScript = Join-Path $ScriptDir "run_manual.bat"

function Write-Message {
    param([string]$Message, [string]$Type = "INFO")
    $Colors = @{
        "INFO" = "Cyan"
        "SUCCESS" = "Green"
        "WARNING" = "Yellow"
        "ERROR" = "Red"
    }
    Write-Host "[$Type] $Message" -ForegroundColor $Colors[$Type]
}

function Get-PythonPath {
    $PythonPaths = @(
        "$env:USERPROFILE\AppData\Local\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "C:\Users\samip\AppData\Local\Programs\Python\Python312\python.exe",
        "python.exe"
    )
    
    foreach ($Path in $PythonPaths) {
        if (Test-Path $Path) {
            return $Path
        }
    }
    return $null
}

function Install-Task {
    Write-Message "Setting up daily automation..." "INFO"
    
    if (-not (Test-Path $AutomationScript)) {
        Write-Message "Automation script not found: $AutomationScript" "ERROR"
        return $false
    }
    
    $PythonPath = Get-PythonPath
    if (-not $PythonPath) {
        Write-Message "Python 3.12 not found. Please install from https://python.org" "ERROR"
        return $false
    }
    
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Write-Message "Removing existing task..." "WARNING"
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    
    $Action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -NoProfile -File `"$AutomationScript`"" `
        -WorkingDirectory $ScriptDir
    
    $Trigger = New-ScheduledTaskTrigger `
        -Daily `
        -At "00:00"
    
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable:$false `
        -DontStopOnIdleEnd `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
        -MultipleInstances "IgnoreNew"
    
    $Principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType "Interactive" `
        -RunLevel "Limited"
    
    $Description = "Runs Noclout scraper daily at midnight to sync products with Supabase database"
    
    try {
        Register-ScheduledTask `
            -TaskName $TaskName `
            -Action $Action `
            -Trigger $Trigger `
            -Settings $Settings `
            -Principal $Principal `
            -Description $Description `
            -Force | Out-Null
        
        Write-Message "Task created successfully!" "SUCCESS"
        return $true
    }
    catch {
        Write-Message "Failed to create task: $_" "ERROR"
        return $false
    }
}

function Remove-Task {
    Write-Message "Removing scheduled task..." "INFO"
    
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Write-Message "Task removed successfully!" "SUCCESS"
    }
    else {
        Write-Message "Task not found" "WARNING"
    }
}

function Show-TaskStatus {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Task) {
        $Info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
        
        Write-Message "Task Status:" "INFO"
        Write-Host "  Name:         $($Task.TaskName)"
        Write-Host "  State:        $($Task.State)"
        Write-Host "  Last Run:     $($Info.LastRunTime)"
        Write-Host "  Last Result:  $($Info.LastTaskResult)"
        Write-Host "  Next Run:     $($Info.NextRunTime)"
        Write-Host ""
    }
    else {
        Write-Message "Task not configured" "WARNING"
        Write-Host ""
    }
}

function Test-Automation {
    Write-Message "Testing automation script..." "INFO"
    
    if (-not (Test-Path $AutomationScript)) {
        Write-Message "Automation script not found!" "ERROR"
        return $false
    }
    
    Write-Message "Automation script exists: $AutomationScript" "SUCCESS"
    
    $PythonPath = Get-PythonPath
    if ($PythonPath) {
        Write-Message "Python found: $PythonPath" "SUCCESS"
    }
    else {
        Write-Message "Python 3.12 not found!" "ERROR"
        return $false
    }
    
    return $true
}

# Main
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Noclout Scraper - Scheduler Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($Uninstall) {
    Remove-Task
}
else {
    if (Test-Automation) {
        if (Install-Task) {
            Write-Host ""
            Show-TaskStatus
            Write-Host ""
            Write-Message "Setup complete!" "SUCCESS"
            Write-Host ""
            Write-Message "To run manually, use:" "INFO"
            Write-Host "  1. Double-click: run_manual.bat"
            Write-Host "  2. Or run: powershell -File run_automated.ps1"
            Write-Host "  3. Or run: python scraper.py"
            Write-Host ""
            Write-Message "Task will run daily at 00:00 (midnight)" "INFO"
            Write-Host ""
            
            if ($RunNow) {
                Write-Message "Running scraper now..." "INFO"
                Write-Host ""
                & $AutomationScript
            }
        }
    }
    else {
        Write-Message "Please fix the errors above before continuing" "ERROR"
        exit 1
    }
}

Write-Host ""
