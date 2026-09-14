[CmdletBinding()]
param(
    [Parameter()]
    [ValidatePattern('^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.duckdns\.org$')]
    [string]$DnsHostname = 'example.duckdns.org',

    [Parameter()]
    [ValidatePattern('^\d{1,3}(?:\.\d{1,3}){3}$')]
    [string]$ExpectedIp = '203.0.113.10'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$StoreRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$CaddyRoot = if ($env:CALYX_CADDY_ROOT) { $env:CALYX_CADDY_ROOT } else { Join-Path $env:ProgramData 'Calyx-Caddy' }
$CaddyExe = Join-Path $CaddyRoot 'caddy.exe'
$CaddyFile = Join-Path $CaddyRoot 'Caddyfile'
$CaddyLauncher = Join-Path $CaddyRoot 'Start-Caddy.cmd'
$SiteLauncher = Join-Path $CaddyRoot 'Start-CalyxSite.cmd'
$CaddyLog = Join-Path $CaddyRoot 'caddy.log'
$SiteLog = Join-Path $CaddyRoot 'calyx-site.log'
$CaddyTaskName = 'Calyx Caddy HTTPS'
$SiteTaskName = 'Calyx EA Store'

function Write-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host ('==> ' + $Message) -ForegroundColor Cyan
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Stop-ExpectedListener {
    param(
        [int]$Port,
        [string]$ExpectedCommandPattern
    )

    $connections = @(
        Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
            Sort-Object OwningProcess -Unique
    )
    foreach ($connection in $connections) {
        $processInfo = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $connection.OwningProcess)
        $commandLine = [string]$processInfo.CommandLine
        if ($commandLine -notmatch $ExpectedCommandPattern) {
            throw "Port $Port is already used by PID $($connection.OwningProcess) ($($processInfo.Name)). Stop that application before running this installer."
        }
        Stop-Process -Id $connection.OwningProcess -Force -ErrorAction Stop
    }
}

function Wait-Http {
    param(
        [string]$Uri,
        [int]$Seconds = 30
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

function Wait-DnsAddress {
    param(
        [string]$Hostname,
        [string]$IpAddress,
        [int]$Seconds = 120
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    $resolvers = @('1.1.1.1', '8.8.8.8')
    do {
        foreach ($resolver in $resolvers) {
            try {
                $addresses = @(
                    Resolve-DnsName -Name $Hostname -Type A -Server $resolver -ErrorAction Stop |
                        Where-Object Type -eq 'A' |
                        Select-Object -ExpandProperty IPAddress
                )
                if ($IpAddress -in $addresses) {
                    return $true
                }
            }
            catch {
                # A newly-created DuckDNS record can take a moment to reach public resolvers.
            }
        }
        Write-Host 'Waiting for the new DuckDNS record to become public...'
        Start-Sleep -Seconds 5
    } while ([DateTime]::UtcNow -lt $deadline)

    return $false
}

if (-not (Test-Administrator)) {
    throw 'Run configDns.bat as Administrator.'
}

Write-Step 'Checking DuckDNS'
if (-not (Wait-DnsAddress -Hostname $DnsHostname -IpAddress $ExpectedIp)) {
    throw "$DnsHostname is not publicly resolving to $ExpectedIp yet. Confirm the DuckDNS value, wait a few minutes, and run this BAT again."
}
Write-Host "$DnsHostname resolves correctly to $ExpectedIp." -ForegroundColor Green

Write-Step 'Preparing the EA website'
$PythonExe = Join-Path $StoreRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) {
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uvCommand) {
        throw 'The website Python environment and uv are both missing. Install uv from https://docs.astral.sh/uv/ and run this BAT again.'
    }
    Push-Location $StoreRoot
    try {
        & $uvCommand.Source sync
        if ($LASTEXITCODE -ne 0) {
            throw 'uv sync failed.'
        }
    }
    finally {
        Pop-Location
    }
}
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python environment was not created at $PythonExe."
}

Write-Step 'Downloading and verifying Caddy'
New-Item -ItemType Directory -Path $CaddyRoot -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$headers = @{
    Accept = 'application/vnd.github+json'
    'User-Agent' = 'Calyx-Caddy-Installer'
}
$release = Invoke-RestMethod -Uri 'https://api.github.com/repos/caddyserver/caddy/releases/latest' -Headers $headers
$zipAsset = @($release.assets | Where-Object name -Match '^caddy_.+_windows_amd64\.zip$') | Select-Object -First 1
$checksumAsset = @($release.assets | Where-Object name -Match 'checksums\.txt$') | Select-Object -First 1
if (-not $zipAsset -or -not $checksumAsset) {
    throw 'The official Caddy Windows package or checksum file could not be found.'
}

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('calyx-caddy-' + [guid]::NewGuid().ToString('N'))
$zipPath = Join-Path $tempRoot $zipAsset.name
$checksumPath = Join-Path $tempRoot $checksumAsset.name
$extractRoot = Join-Path $tempRoot 'expanded'
New-Item -ItemType Directory -Path $tempRoot, $extractRoot -Force | Out-Null
try {
    Invoke-WebRequest -UseBasicParsing -Uri $zipAsset.browser_download_url -OutFile $zipPath -Headers $headers
    Invoke-WebRequest -UseBasicParsing -Uri $checksumAsset.browser_download_url -OutFile $checksumPath -Headers $headers
    $checksumLine = Get-Content -LiteralPath $checksumPath |
        Where-Object { $_.TrimEnd().EndsWith($zipAsset.name, [StringComparison]::OrdinalIgnoreCase) } |
        Select-Object -First 1
    if (-not $checksumLine) {
        throw "No checksum was published for $($zipAsset.name)."
    }
    $expectedHash = ($checksumLine.Trim() -split '\s+')[0].ToLowerInvariant()
    if ($expectedHash -notmatch '^[0-9a-f]{128}$') {
        throw "The published checksum for $($zipAsset.name) is not a valid SHA-512 hash."
    }
    $actualHash = (Get-FileHash -Algorithm SHA512 -LiteralPath $zipPath).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw 'The downloaded Caddy archive failed SHA-512 verification.'
    }
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot -Force
    Copy-Item -LiteralPath (Join-Path $extractRoot 'caddy.exe') -Destination $CaddyExe -Force
}
finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "Installed $(& $CaddyExe version)." -ForegroundColor Green

Write-Step 'Writing the HTTPS reverse-proxy configuration'
if (Test-Path -LiteralPath $CaddyFile) {
    $backupName = 'Caddyfile.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    Copy-Item -LiteralPath $CaddyFile -Destination (Join-Path $CaddyRoot $backupName)
}
@"
$DnsHostname {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8080
}
"@ | Set-Content -LiteralPath $CaddyFile -Encoding ascii

@"
@echo off
cd /d "$CaddyRoot"
"$CaddyExe" run --config "$CaddyFile" --adapter caddyfile >> "$CaddyLog" 2>&1
"@ | Set-Content -LiteralPath $CaddyLauncher -Encoding ascii

@"
@echo off
cd /d "$StoreRoot"
"$PythonExe" -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --proxy-headers --forwarded-allow-ips 127.0.0.1 >> "$SiteLog" 2>&1
"@ | Set-Content -LiteralPath $SiteLauncher -Encoding ascii

& $CaddyExe validate --config $CaddyFile --adapter caddyfile
if ($LASTEXITCODE -ne 0) {
    throw 'Caddy rejected the generated configuration.'
}

Write-Step 'Opening Windows firewall ports 80 and 443'
foreach ($port in 80, 443) {
    $ruleName = "Calyx Caddy TCP $port"
    if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port |
            Out-Null
    }
}

Write-Step 'Installing automatic startup tasks'
Stop-ScheduledTask -TaskName $CaddyTaskName -ErrorAction SilentlyContinue
Stop-ScheduledTask -TaskName $SiteTaskName -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Stop-ExpectedListener -Port 80 -ExpectedCommandPattern 'caddy'
Stop-ExpectedListener -Port 443 -ExpectedCommandPattern 'caddy'
Stop-ExpectedListener -Port 8080 -ExpectedCommandPattern 'uvicorn.+app\.main:app'

$caddyAction = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\cmd.exe" -Argument "/d /c `"$CaddyLauncher`""
$caddyTrigger = New-ScheduledTaskTrigger -AtStartup
$caddyPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$caddyTask = New-ScheduledTask -Action $caddyAction -Trigger $caddyTrigger -Principal $caddyPrincipal
Register-ScheduledTask -TaskName $CaddyTaskName -InputObject $caddyTask -Force | Out-Null

$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$siteAction = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\cmd.exe" -Argument "/d /c `"$SiteLauncher`""
$siteTrigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$sitePrincipal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Highest
$siteTask = New-ScheduledTask -Action $siteAction -Trigger $siteTrigger -Principal $sitePrincipal
Register-ScheduledTask -TaskName $SiteTaskName -InputObject $siteTask -Force | Out-Null

Start-ScheduledTask -TaskName $SiteTaskName
if (-not (Wait-Http -Uri 'http://127.0.0.1:8080/api/health' -Seconds 45)) {
    throw "The EA website did not start. Check $SiteLog."
}

Start-ScheduledTask -TaskName $CaddyTaskName
$finalLink = 'https://' + $DnsHostname
$httpsReady = Wait-Http -Uri $finalLink -Seconds 45

Write-Host ''
Write-Host '============================================================' -ForegroundColor Green
if ($httpsReady) {
    Write-Host 'HTTPS IS READY' -ForegroundColor Green
}
else {
    Write-Host 'CADDY STARTED, BUT PUBLIC HTTPS IS NOT REACHABLE YET' -ForegroundColor Yellow
    Write-Host 'Confirm that TCP 80 and 443 are also allowed in the OVH network firewall.' -ForegroundColor Yellow
}
Write-Host ('FINAL LINK: ' + $finalLink) -ForegroundColor White
Write-Host ('Caddy log: ' + $CaddyLog)
Write-Host ('Website log: ' + $SiteLog)
Write-Host 'The website now listens privately on 127.0.0.1:8080.'
Write-Host '============================================================' -ForegroundColor Green
