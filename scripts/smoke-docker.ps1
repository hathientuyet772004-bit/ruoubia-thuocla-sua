param(
    [string]$BaseUrl = "http://localhost"
)

$ErrorActionPreference = "Stop"

docker compose up -d --build
docker compose up -d --force-recreate nginx

Start-Sleep -Seconds 5

$checks = @(
    @{ Name = "frontend"; Url = "$BaseUrl/" },
    @{ Name = "health"; Url = "$BaseUrl/api/health" },
    @{ Name = "ready"; Url = "$BaseUrl/api/ready" }
)

foreach ($check in $checks) {
    $response = Invoke-WebRequest -UseBasicParsing $check.Url
    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
        throw "$($check.Name) returned HTTP $($response.StatusCode)"
    }
    Write-Host "$($check.Name): HTTP $($response.StatusCode)"
}

docker compose ps
