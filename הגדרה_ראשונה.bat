@echo off
chcp 65001 > nul
echo.
echo ============================================================
echo    📚 סוכן הספרייה — הגדרה ראשונה
echo ============================================================
echo.
echo  כדי לפעול, הסוכן צריך מפתח API של Anthropic.
echo  תוכלי לקבל מפתח ב: https://console.anthropic.com/
echo.
set /p APIKEY="  הדביקי את המפתח (sk-ant-...): "
echo.

if "%APIKEY%"=="" (
    echo ❌ לא הוזן מפתח
    pause
    exit /b 1
)

echo ANTHROPIC_API_KEY=%APIKEY% > "%~dp0.env"
echo.
echo ✅ המפתח נשמר בקובץ .env
echo    עכשיו תוכלי להפעיל את הסוכן דרך הפעל.bat
echo.
pause
