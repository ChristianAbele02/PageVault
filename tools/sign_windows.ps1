<#
.SYNOPSIS
    Authenticode-sign a PageVault build artefact (executable or installer).

.DESCRIPTION
    Signs the target file with SHA-256 plus an RFC3161 timestamp (so signatures remain
    valid after the certificate expires). Prefers signtool.exe from the Windows SDK (used
    on CI runners); when the SDK is absent it falls back to PowerShell's built-in
    Set-AuthenticodeSignature, so signing works on a plain Windows machine too.

    The certificate is supplied either as a .pfx file (-PfxPath) or as a base64-encoded
    blob (-CertBase64, used by CI from a GitHub secret) so the private key never has to
    live in the repository.

    The script confirms a signature was applied. A `signtool verify` failure is only a
    warning: a self-signed certificate that has not been imported into the machine's trust
    store will not verify, which is expected for private use.

.PARAMETER Path
    File to sign, e.g. dist\PageVault\PageVault.exe.

.PARAMETER PfxPath
    Path to a PFX certificate file.

.PARAMETER CertBase64
    Base64-encoded PFX content (alternative to -PfxPath). Written to a temp file that is
    removed afterwards.

.PARAMETER Password
    PFX password.

.PARAMETER TimestampUrl
    RFC3161 timestamp server (default: http://timestamp.digicert.com).

.EXAMPLE
    .\tools\sign_windows.ps1 -Path dist\PageVault\PageVault.exe -PfxPath certs\pagevault-codesign.pfx -Password (Read-Host -AsSecureString)
#>
[CmdletBinding(DefaultParameterSetName = 'Pfx')]
param(
    [Parameter(Mandatory)] [string] $Path,
    [Parameter(Mandatory, ParameterSetName = 'Pfx')] [string] $PfxPath,
    [Parameter(Mandatory, ParameterSetName = 'Base64')] [string] $CertBase64,
    [Parameter(Mandatory)] [string] $Password,
    [string] $TimestampUrl = 'http://timestamp.digicert.com'
)

$ErrorActionPreference = 'Stop'

function Find-SignTool {
    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $roots = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin",
        "${env:ProgramFiles}\Windows Kits\10\bin"
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        $found = Get-ChildItem -Path $root -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\x64\\' } |
            Sort-Object FullName -Descending | Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

if (-not (Test-Path $Path)) { throw "File to sign not found: $Path" }

$tempPfx = $null
try {
    if ($PSCmdlet.ParameterSetName -eq 'Base64') {
        $tempPfx = Join-Path ([System.IO.Path]::GetTempPath()) ("pv_" + [guid]::NewGuid().ToString('N') + ".pfx")
        [System.IO.File]::WriteAllBytes($tempPfx, [System.Convert]::FromBase64String($CertBase64))
        $PfxPath = $tempPfx
    }
    if (-not (Test-Path $PfxPath)) { throw "Certificate not found: $PfxPath" }

    $signtool = Find-SignTool
    if ($signtool) {
        Write-Host "Signing with signtool: $signtool"
        & $signtool sign /fd SHA256 /f $PfxPath /p $Password /tr $TimestampUrl /td SHA256 /v $Path
        if ($LASTEXITCODE -ne 0) { throw "signtool sign failed with exit code $LASTEXITCODE" }
    }
    else {
        Write-Host "signtool not found; signing with Set-AuthenticodeSignature (no Windows SDK required)."
        $flags = [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]'Exportable'
        $cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($PfxPath, $Password, $flags)
        $result = Set-AuthenticodeSignature -FilePath $Path -Certificate $cert `
            -HashAlgorithm SHA256 -TimestampServer $TimestampUrl
        if (-not $result.SignerCertificate) {
            throw "Signing failed: $($result.StatusMessage)"
        }
    }

    $sig = Get-AuthenticodeSignature -FilePath $Path
    if (-not $sig.SignerCertificate) { throw "No signature present after signing: $Path" }
    Write-Host "Signed by: $($sig.SignerCertificate.Subject) (status: $($sig.Status))"

    if ($signtool) {
        & $signtool verify /pa /v $Path
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "signtool verify reported the signature is not trusted on this machine. This is expected for a self-signed certificate that has not been imported into the trust store."
        }
    }
}
finally {
    if ($tempPfx -and (Test-Path $tempPfx)) { Remove-Item -LiteralPath $tempPfx -Force }
}
