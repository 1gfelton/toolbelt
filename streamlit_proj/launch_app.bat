@echo off
echo Starting Streamlit App...
echo.
echo If this is your first time running, make sure you have installed:
echo   pip install streamlit
echo.
echo The app will open in your default web browser.
echo To stop the app, press Ctrl+C in this window.
echo.
pause

cd /d "%~dp0"
streamlit run streamlit_app.py

pause
