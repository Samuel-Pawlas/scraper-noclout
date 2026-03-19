# Noclout Scraper - Task Scheduler Setup
# Run this script once to set up daily automation at midnight

param(
    [switch]$Uninstall,
    [switch]$RunNow
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) {
    $ScriptDir = $PSScriptRoot
}
if (-not $ScriptDir) {
    $ScriptDir = "C:\Finds\Scrapers\scraper-noclout"
}

$TaskName = "NocloutDailyScraper"
$AutomationScript = Join-Path $ScriptDir "run_automated.ps1"

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

function Install-Task {
    Write-Message "Setting up daily automation..."
    
    # Check if script exists
    if (-not (Test-Path $AutomationScript)) {
        Write-Message "Automation script not found: $AutomationScript" "ERROR"
        return $false
    }
    
    # Remove existing task if present
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Write-Message "Removing existing task..." "WARNING"
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    
    # Create action
    $Action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$AutomationScript`"" `
        -WorkingDirectory $ScriptDir
    
    # Create trigger - daily at midnight
    $Trigger = New-ScheduledTaskTrigger `
        -Daily `
        -At "00:00"
    
    # Create settings
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable:$false `
        -DontStopOnIdleEnd `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    
    # Create principal (run as current user)
    $Principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType Interactive `
        -RunLevel Limited
    
    # Register task
    try {
        Register-ScheduledTask `
            -TaskName $TaskName `
            -Action $Action `
            -Trigger $Trigger `
            -Settings $Settings `
            -Principal $Principal `
            -Description "Runs Noclout scraper daily at midnight" `
            -Force
        
        Write-Message "Task created successfully!" "SUCCESS"
        Write-Message "Task will run daily at 00:00 (midnight)" "INFO"
        return $true
    }
    catch {
        Write-Message "Failed to create task: $_" "ERROR"
        return $false
    }
}

function Remove-Task {
    Write-Message "Removing scheduled task..."
    
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Message "Task removed successfully!" "SUCCESS"
    }
    else {
        Write-Message "Task not found" "WARNING"
    }
}

function Show-TaskStatus {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Task) {
        Write-Message "Task Status:" "INFO"
        Write-Host "  Name: $($Task.TaskName)"
        Write-Host "  State: $($Task.State)"
        Write-Host "  Last Run: $(($Task | Get-ScheduledTaskInfo).LastRunTime)"
        Write-Host "  Next Run: $(($Task | Get-ScheduledTaskInfo).NextRunTime)"
    }
    else {
        Write-Message "Task not configured" "WARNING"
    }
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
    if (Install-Task) {
        Write-Host ""
        Show-TaskStatus
        Write-Host ""
        Write-Message "To run manually, use:" "INFO"
        Write-Host "  1. Double-click: run_manual.bat"
        Write-Host "  2. Or run: $AutomationScript"
        Write-Host ""
        
        if ($RunNow) {
            Write-Message "Running scraper now..." "INFO"
            & $AutomationScript
        }
    }
}

Write-Host ""
