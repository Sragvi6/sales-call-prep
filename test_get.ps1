# test_get.ps1
# Diagnostic check for file status

if (-not (Test-Path .env)) {
    Write-Host "No .env"
    exit 1
}

$envVars = @{}
Get-Content .env | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line -split '=', 2
        $envVars[$parts[0].Trim()] = $parts[1].Trim()
    }
}

$Token = $envVars["GITHUB_TOKEN"]
$Username = $envVars["GITHUB_USERNAME"]

$headers = @{
    "Authorization" = "Bearer $Token"
    "Accept"        = "application/vnd.github.v3+json"
    "User-Agent"    = "PowerShell-GitHub-Pusher"
}

$file = "app.py"
$url = "https://api.github.com/repos/$Username/sales-call-prep/contents/$file?ref=main"

try {
    Write-Host "Getting file metadata from: $url"
    $res = Invoke-RestMethod -Uri $url -Method Get -Headers $headers
    Write-Host "Success! File found. SHA = $($res.sha)" -ForegroundColor Green
} catch {
    Write-Host "Failed: $_" -ForegroundColor Red
    if ($_.Exception.Response) {
        $r = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "API Response: $($r.ReadToEnd())" -ForegroundColor Red
    }
}
