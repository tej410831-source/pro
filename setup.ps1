# Setup Script for Windows PowerShell

Write-Host "🚀 Setting up Python Environment for Advanced Code Analyzer..." -ForegroundColor Cyan

# 1. Create Virtual Environment
if (!(Test-Path "venv")) {
    Write-Host "📦 Creating virtual environment 'venv'..." -ForegroundColor Yellow
    python -m venv venv
} else {
    Write-Host "✓ Virtual environment already exists." -ForegroundColor Green
}

# 2. Upgrade pip
Write-Host "⬆️  Upgrading pip..." -ForegroundColor Yellow
.\venv\Scripts\python.exe -m pip install --upgrade pip

# 3. Install Dependencies
Write-Host "📥 Installing dependencies from requirements.txt..." -ForegroundColor Yellow
.\venv\Scripts\pip.exe install -r requirements.txt

Write-Host "`n✅ Setup Complete!" -ForegroundColor Green
Write-Host "`nTo analyze your project, run:" -ForegroundColor Cyan
Write-Host ".\venv\Scripts\python.exe main.py analyze . --generate-fixes" -ForegroundColor White
Write-Host "`nOr activate the environment manually:" -ForegroundColor Cyan
Write-Host ".\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "python main.py analyze . --generate-fixes" -ForegroundColor White
