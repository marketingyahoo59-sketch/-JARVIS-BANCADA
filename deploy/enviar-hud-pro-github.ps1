# Roda no PC (PowerShell) na pasta do projeto clonado do GitHub
# Atualiza o GitHub para o Render puxar o HUD novo (Sr. Igor / Config / Sistemas)
$ErrorActionPreference = "Stop"
Write-Host "1) Clone ou abre a pasta do repo -JARVIS-BANCADA"
Write-Host "2) Se ainda nao tiver o codigo novo, no Cursor: Clone do agent OU baixe ZIP do agent"
Write-Host ""
Write-Host "Comandos tipicos (na pasta do projeto atualizado):"
Write-Host '  git add -A'
Write-Host '  git commit -m "HUD JARVIS Sr. Igor + Sistemas + Config + keep-alive"'
Write-Host '  git push origin main'
Write-Host ""
Write-Host "Depois no Render: Manual Deploy -> Deploy latest commit"
Write-Host "URL: https://jarvis-bancada.onrender.com/"
