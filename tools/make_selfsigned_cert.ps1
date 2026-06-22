<#
.SYNOPSIS
    Generate a SELF-SIGNED code-signing certificate for PRIVATE use.

.DESCRIPTION
    Creates a self-signed Authenticode certificate and exports it as a password-protected
    PFX (used to sign builds) and a CER (used to establish trust). Importing the CER into
    "Trusted Root Certification Authorities" and "Trusted Publishers" on a machine removes
    the SmartScreen "unknown publisher" prompt for PageVault ON THAT MACHINE ONLY.

    This does NOT make the app trusted for the public. For a public release, use a
    certificate from a Certificate Authority, or a service such as SignPath (free for
    open-source projects). See the "Code signing" section of the README.

.PARAMETER OutDir
    Output directory for the .pfx and .cer (default: .\certs, which is git-ignored).

.PARAMETER Password
    Password protecting the exported PFX. Prompted securely if omitted.

.PARAMETER Subject
    Publisher name shown on the signature (default: PageVault).

.PARAMETER YearsValid
    Validity period in years (default: 3).

.EXAMPLE
    .\tools\make_selfsigned_cert.ps1
#>
param(
    [string] $OutDir = (Join-Path $PSScriptRoot '..\certs'),
    [System.Security.SecureString] $Password,
    [string] $Subject = 'PageVault',
    [int] $YearsValid = 3
)

$ErrorActionPreference = 'Stop'

if (-not $Password) { $Password = Read-Host -AsSecureString "PFX export password" }

$OutDir = (New-Item -ItemType Directory -Force -Path $OutDir).FullName

$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject "CN=$Subject" `
    -KeyUsage DigitalSignature `
    -KeyAlgorithm RSA -KeyLength 3072 `
    -CertStoreLocation Cert:\CurrentUser\My `
    -NotAfter (Get-Date).AddYears($YearsValid) `
    -FriendlyName "$Subject code-signing (self-signed)"

$pfxPath = Join-Path $OutDir 'pagevault-codesign.pfx'
$cerPath = Join-Path $OutDir 'pagevault-codesign.cer'

Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $Password | Out-Null
Export-Certificate -Cert $cert -FilePath $cerPath | Out-Null

# The PFX is the portable source of truth; remove the working copy from the user store.
Remove-Item -Path ("Cert:\CurrentUser\My\" + $cert.Thumbprint) -Force

Write-Host ""
Write-Host "Created self-signed code-signing certificate (PRIVATE USE ONLY)."
Write-Host "  PFX (sign with this):  $pfxPath"
Write-Host "  CER (import to trust): $cerPath"
Write-Host "  Thumbprint:            $($cert.Thumbprint)"
Write-Host ""
Write-Host "Trust the app on a machine (run PowerShell as Administrator):"
Write-Host "  Import-Certificate -FilePath '$cerPath' -CertStoreLocation Cert:\LocalMachine\Root"
Write-Host "  Import-Certificate -FilePath '$cerPath' -CertStoreLocation Cert:\LocalMachine\TrustedPublisher"
Write-Host ""
Write-Host "Sign a build:"
Write-Host "  .\tools\sign_windows.ps1 -Path dist\PageVault\PageVault.exe -PfxPath '$pfxPath' -Password (Read-Host -AsSecureString)"
Write-Host ""
Write-Host "For CI signing, copy the base64 of the PFX into the WINDOWS_CERT_BASE64 repo secret:"
Write-Host "  [Convert]::ToBase64String([IO.File]::ReadAllBytes('$pfxPath')) | Set-Clipboard"
