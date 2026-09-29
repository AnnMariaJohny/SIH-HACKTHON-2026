@echo off
cd /d "%~dp0"
echo Starting OCEANOVA local SAR analysis service...
if exist "%~dp0backend\model\weights\Eclipso_Final_UNet.pt" (
    set "ECLIPSO_CHECKPOINT=%~dp0backend\model\weights\Eclipso_Final_UNet.pt"
    echo Using the included Garcia-trained oil-spill checkpoint.
) else (
    echo ERROR: The Garcia-INPE model checkpoint is missing from backend\model\weights.
    echo Re-extract the complete OCEANOVA ZIP and try again.
    pause
    exit /b 1
)
echo Installing or checking the Python backend dependencies...
set "OCEANOVA_DEPS=%TEMP%\oceanova-python-deps"
if not exist "%OCEANOVA_DEPS%\.oceanova-ready" (
    python -m pip install --upgrade --target "%OCEANOVA_DEPS%" -r "%~dp0backend\requirements.txt"
    if errorlevel 1 (
        echo.
        echo Dependency installation failed. Check the pip error above and your internet connection.
        pause
        exit /b 1
    )
    echo ready>"%OCEANOVA_DEPS%\.oceanova-ready"
    if errorlevel 1 (
        echo Could not write the dependency marker under %OCEANOVA_DEPS%.
        pause
        exit /b 1
    )
    echo ready>"%OCEANOVA_DEPS%\.oceanova-scipy-ready"
    echo Dependencies installed.
) else (
    echo Backend dependencies are already installed.
)
if not exist "%OCEANOVA_DEPS%\.oceanova-scipy-ready" (
    python -m pip install --upgrade --target "%OCEANOVA_DEPS%" "scipy>=1.11"
    if errorlevel 1 (
        echo.
        echo SciPy installation failed. Check the pip error above and your internet connection.
        pause
        exit /b 1
    )
    echo ready>"%OCEANOVA_DEPS%\.oceanova-scipy-ready"
)
if not exist "%OCEANOVA_DEPS%\.oceanova-search-ready" (
    python -m pip install --upgrade --target "%OCEANOVA_DEPS%" "httpx>=0.27" "websockets>=14"
    if errorlevel 1 (
        echo.
        echo Nearby search dependencies failed to install. Check the pip error above and your internet connection.
        pause
        exit /b 1
    )
    echo ready>"%OCEANOVA_DEPS%\.oceanova-search-ready"
)
set "PYTHONPATH=%OCEANOVA_DEPS%;%PYTHONPATH%"
echo When the server is ready, open http://127.0.0.1:8000 in your browser.
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
echo.
echo The service stopped. If Python reports missing packages, install them with:
echo python -m pip install -r backend\requirements.txt
pause
