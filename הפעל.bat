@echo off
chcp 65001 > nul
echo.
echo ============================================================
echo    📚 סוכן הספרייה — ניתוח ספרותי מעמיק
echo ============================================================
echo.
set /p BOOK="  שם הספר: "
set /p AUTHOR="  שם הסופר/ת: "
echo.
python "%~dp0book_agent.py" "%BOOK%" "%AUTHOR%"
echo.
pause
