# Instalação da Triagem no Windows.
#
# Clique com o botão direito neste arquivo e escolha "Executar com o PowerShell".
# Se o Windows reclamar de permissão, abra o PowerShell e rode:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\instalar-windows.ps1

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

function Titulo($texto) {
    Write-Host ""
    Write-Host "== $texto" -ForegroundColor Cyan
}

function Aviso($texto) { Write-Host "   $texto" -ForegroundColor Yellow }
function Certo($texto) { Write-Host "   $texto" -ForegroundColor Green }

Write-Host ""
Write-Host "  Triagem de curriculos - instalacao" -ForegroundColor White
Write-Host "  ----------------------------------"

# ---------------------------------------------------------------- Python

Titulo "Procurando o Python"

$python = $null
foreach ($candidato in @("py -3.12", "py -3.11", "py -3.10", "py -3", "python")) {
    $partes = $candidato.Split(" ")
    $exe = $partes[0]
    $args = @()
    if ($partes.Length -gt 1) { $args = $partes[1..($partes.Length - 1)] }

    $encontrado = Get-Command $exe -ErrorAction SilentlyContinue
    if (-not $encontrado) { continue }

    try {
        $versao = & $exe @args --version 2>&1
    } catch { continue }

    if ($versao -match "Python 3\.(1[0-9]|[2-9][0-9])") {
        $python = $candidato
        Certo "Encontrado: $versao"
        break
    }
}

if (-not $python) {
    Aviso "Python 3.10 ou mais novo nao foi encontrado."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "   Posso instalar agora pelo winget (leva alguns minutos)."
        $resposta = Read-Host "   Instalar o Python 3.12? [S/n]"
        if ($resposta -eq "" -or $resposta -match "^[sSyY]") {
            winget install --id Python.Python.3.12 --source winget `
                --accept-package-agreements --accept-source-agreements
            Aviso "Feche esta janela, abra outra e rode o instalador de novo."
            Read-Host "   Enter para sair"
            exit 0
        }
    }
    Aviso "Baixe em https://www.python.org/downloads/ e marque 'Add python.exe to PATH'."
    Read-Host "   Enter para sair"
    exit 1
}

$partes = $python.Split(" ")
$pyExe = $partes[0]
$pyArgs = @()
if ($partes.Length -gt 1) { $pyArgs = $partes[1..($partes.Length - 1)] }

# ---------------------------------------------------------------- Ambiente

Titulo "Preparando o ambiente"

if (-not (Test-Path ".venv")) {
    & $pyExe @pyArgs -m venv .venv
    Certo "Ambiente criado em .venv"
} else {
    Certo "Ambiente .venv ja existia"
}

$venvPy = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Aviso "Nao consegui criar o ambiente virtual. Instalacao interrompida."
    Read-Host "   Enter para sair"
    exit 1
}

Titulo "Instalando as bibliotecas"
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Aviso "A instalacao das bibliotecas falhou. Confira sua conexao e tente de novo."
    Read-Host "   Enter para sair"
    exit 1
}
Certo "Bibliotecas instaladas"

# ---------------------------------------------------------------- .env

Titulo "Configuracao"

if (-not (Test-Path ".env")) {
    $segredo = & $venvPy -c "import secrets; print(secrets.token_urlsafe(48))"
    $conteudo = Get-Content ".env.example" -Raw -Encoding UTF8
    $conteudo = $conteudo -replace "TRIAGEM_SECRET_KEY=", "TRIAGEM_SECRET_KEY=$segredo"

    Write-Host "   A chave da Anthropic pode ficar em branco agora e ser cadastrada"
    Write-Host "   depois, dentro do sistema, na tela de Configuracoes."
    $chave = Read-Host "   Chave da Anthropic (sk-ant-...) ou Enter para pular"
    if ($chave.Trim() -ne "") {
        $conteudo = $conteudo -replace "ANTHROPIC_API_KEY=", "ANTHROPIC_API_KEY=$($chave.Trim())"
    }

    Set-Content ".env" $conteudo -Encoding UTF8 -NoNewline
    Certo "Arquivo .env criado com um segredo novo"
} else {
    Certo "Arquivo .env ja existia - mantido como estava"
}

# ---------------------------------------------------------------- LibreOffice

$soffice = Get-Command soffice -ErrorAction SilentlyContinue
if (-not $soffice) {
    $caminhos = @(
        "C:\Program Files\LibreOffice\program\soffice.exe",
        "C:\Program Files (x86)\LibreOffice\program\soffice.exe"
    )
    $achou = $false
    foreach ($c in $caminhos) { if (Test-Path $c) { $achou = $true } }
    if (-not $achou) {
        Titulo "Opcional"
        Aviso "LibreOffice nao encontrado. Sem ele, curriculos em .doc e .rtf antigos"
        Aviso "sao recusados no upload. PDF, .docx, .txt, .csv e .xlsx funcionam normal."
        Aviso "Se quiser suporte a .doc: winget install TheDocumentFoundation.LibreOffice"
    }
}

# ---------------------------------------------------------------- Atalho

Titulo "Criando o atalho de inicio"

$iniciar = @"
`$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent `$MyInvocation.MyCommand.Path)
Write-Host ""
Write-Host "  Triagem no ar em http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  Feche esta janela para desligar." -ForegroundColor DarkGray
Write-Host ""
Start-Process "http://127.0.0.1:8000"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"@
Set-Content "iniciar.ps1" $iniciar -Encoding UTF8
Certo "Criado iniciar.ps1"

$conectar = @"
`$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent `$MyInvocation.MyCommand.Path)
& ".\.venv\Scripts\python.exe" conectar_claude.py
Read-Host "`n  Enter para fechar"
"@
Set-Content "conectar-claude.ps1" $conectar -Encoding UTF8
Certo "Criado conectar-claude.ps1"

# ---------------------------------------------------------------- Claude

Titulo "Claude nesta maquina"

$configClaude = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
if (Test-Path (Split-Path -Parent $configClaude)) {
    Certo "Claude Desktop encontrado"
    Write-Host "   Depois de criar sua conta na Triagem, rode conectar-claude.ps1"
    Write-Host "   para o Claude passar a enxergar suas vagas e curriculos."
} else {
    Aviso "Claude Desktop nao encontrado."
    Aviso "Sem ele, a Triagem funciona normal pelo navegador - voce so nao vai"
    Aviso "poder fazer a triagem conversando. Para ter isso, instale o Claude"
    Aviso "Desktop em https://claude.ai/download e rode conectar-claude.ps1."
}

Write-Host ""
Write-Host "  Pronto." -ForegroundColor Green
Write-Host ""
Write-Host "  1. Clique com o botao direito em iniciar.ps1 -> Executar com o PowerShell"
Write-Host "  2. No navegador que abrir, crie sua conta"
Write-Host "  3. Em Configuracoes, cole sua chave da Anthropic (ou pule, se for"
Write-Host "     usar so pelo Claude) e defina um teto de gasto"
Write-Host "  4. Opcional: rode conectar-claude.ps1 para ligar ao Claude Desktop"
Write-Host ""
Write-Host "  Tudo roda nesta maquina. Nenhum curriculo sai daqui, a nao ser o" -ForegroundColor DarkGray
Write-Host "  texto enviado para a Anthropic durante a avaliacao." -ForegroundColor DarkGray
Write-Host ""

$agora = Read-Host "  Abrir agora? [S/n]"
if ($agora -eq "" -or $agora -match "^[sSyY]") {
    Start-Process "http://127.0.0.1:8000"
    & $venvPy -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}
