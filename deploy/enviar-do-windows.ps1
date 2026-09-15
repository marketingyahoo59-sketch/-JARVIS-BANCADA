# Rode no PowerShell do Windows (Cursor no PC, na pasta do projeto JARVIS).
$ErrorActionPreference = "Stop"
$HostName = "34.122.2.87"
$Users = @("ubuntu", "root", "opc", "igor")
$KeyCandidates = @(
  "$env:USERPROFILE\.ssh\id_ed25519",
  "$env:USERPROFILE\.ssh\id_rsa",
  "$env:USERPROFILE\.ssh\google_compute_engine",
  "$env:USERPROFILE\.ssh\oracle.pem",
  "$env:USERPROFILE\.ssh\ssh-key-2024.key",
  "$env:USERPROFILE\.ssh\id_ecdsa"
)

$Key = $KeyCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Key) {
  Write-Host "Sem chave em $env:USERPROFILE\.ssh — listando pasta:"
  Get-ChildItem "$env:USERPROFILE\.ssh" -ErrorAction SilentlyContinue
  throw "Coloque a chave privada SSH nessa pasta ou ajuste o script."
}

$Repo = Resolve-Path (Join-Path $PSScriptRoot "..")
Write-Host "Chave: $Key"
Write-Host "Repo:  $Repo"

$User = $null
foreach ($u in $Users) {
  Write-Host "Testando ${u}@${HostName} ..."
  & ssh -i $Key -o StrictHostKeyChecking=no -o ConnectTimeout=8 -o BatchMode=yes "$u@$HostName" "echo OK" 2>$null
  if ($LASTEXITCODE -eq 0) { $User = $u; break }
}
if (-not $User) { throw "Nenhum usuario SSH funcionou com essa chave." }
Write-Host "Login: $User@$HostName"

$Tar = Join-Path $env:TEMP "jarvis-src.tgz"
Push-Location $Repo
if (Get-Command tar -ErrorAction SilentlyContinue) {
  tar -czf $Tar --exclude=.venv --exclude=__pycache__ --exclude=.git --exclude=data/cases --exclude=data/uploads *
} else {
  throw "Instale tar ou use WSL."
}
Pop-Location

scp -i $Key -o StrictHostKeyChecking=no $Tar "${User}@${HostName}:/tmp/jarvis-src.tgz"
scp -i $Key -o StrictHostKeyChecking=no (Join-Path $PSScriptRoot "install-jarvis.sh") "${User}@${HostName}:/tmp/install-jarvis.sh"
if (Test-Path (Join-Path $Repo ".env")) {
  scp -i $Key -o StrictHostKeyChecking=no (Join-Path $Repo ".env") "${User}@${HostName}:/tmp/jarvis.env"
}

ssh -i $Key -o StrictHostKeyChecking=no "$User@$HostName" "rm -rf /tmp/jarvis-src && mkdir -p /tmp/jarvis-src && tar -xzf /tmp/jarvis-src.tgz -C /tmp/jarvis-src && sudo bash /tmp/install-jarvis.sh"

Write-Host "Pronto: https://34-122-2-87.sslip.io"
