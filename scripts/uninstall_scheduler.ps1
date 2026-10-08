$ErrorActionPreference = "Stop"

@(
    "GlimpseOfThoughts-11AM",
    "GlimpseOfThoughts-430PM",
    "GlimpseOfThoughts-930PM"
) | ForEach-Object {
    Unregister-ScheduledTask -TaskName $_ -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed $_ (if it existed)."
}
