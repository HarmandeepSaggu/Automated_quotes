param(
    [string]$ProjectPath = "",
    [string]$MorningTime = "11:00",
    [string]$EveningTime = "16:30",
    [string]$NightTime = "21:30"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectPath = (Resolve-Path $ProjectPath).Path
}

$runner = Join-Path $ProjectPath "scripts\run_daily.bat"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "Could not find the project runner: $runner"
}

function Convert-ToScheduleTime([string]$Value) {
    try {
        return [datetime]::ParseExact(
            $Value,
            "HH:mm",
            [Globalization.CultureInfo]::InvariantCulture
        )
    } catch {
        throw "Invalid time '$Value'. Use 24-hour HH:mm format, for example 16:30."
    }
}

$slots = @(
    @{ Name = "11AM"; RunId = "morning"; Time = Convert-ToScheduleTime $MorningTime },
    @{ Name = "430PM"; RunId = "evening"; Time = Convert-ToScheduleTime $EveningTime },
    @{ Name = "930PM"; RunId = "night"; Time = Convert-ToScheduleTime $NightTime }
)

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType InteractiveToken `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

foreach ($slot in $slots) {
    $taskName = "GlimpseOfThoughts-$($slot.Name)"
    $time = $slot.Time
    $at = (Get-Date).Date.AddHours($time.Hour).AddMinutes($time.Minute)
    if ($at -le (Get-Date)) {
        $at = $at.AddDays(1)
    }
    $trigger = New-ScheduledTaskTrigger -Daily -At $at

    # The doubled quotes are required by cmd.exe when the project path contains spaces.
    $arguments = '/d /c ""{0}" --run-id {1}"' -f $runner, $slot.RunId
    $action = New-ScheduledTaskAction `
        -Execute $env:ComSpec `
        -Argument $arguments `
        -WorkingDirectory $ProjectPath

    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Description "Automatically create and publish the $($slot.RunId) Glimpse Of Thoughts post." `
        -Force | Out-Null

    Write-Host "Installed $taskName at $($slot.Time.ToString('HH:mm')) (computer local time)."
}

Write-Host ""
Write-Host "Automation is installed. The computer should be powered on and the Windows user should be signed in at posting time."
Write-Host "To remove these tasks, run: .\scripts\uninstall_scheduler.ps1"
