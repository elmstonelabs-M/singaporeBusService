param(
    [string]$HostName = "35.197.135.48",
    [string]$UserName = "devlop",
    [int]$Port = 22
)

$ErrorActionPreference = "Stop"

$tempDir = Join-Path $env:TEMP "codex-ssh"
$tempKey = Join-Path $tempDir "id_ed25519"

if (-not (Test-Path $tempKey)) {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $sourceKey = Join-Path $projectRoot ".ssh-temp\id_ed25519"

    if (-not (Test-Path $sourceKey)) {
        throw "SSH private key not found: $sourceKey"
    }

    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    Copy-Item $sourceKey $tempKey -Force

    # OpenSSH on Windows rejects keys that are readable by broad principals.
    icacls $tempKey /inheritance:r | Out-Null
    icacls $tempKey /grant:r "${env:USERNAME}:R" | Out-Null
}

ssh -i $tempKey -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -p $Port "$UserName@$HostName"
