@echo off
echo ========================================================
echo    Pushing Passport Photo App to GitHub
echo    Target: https://github.com/urfavsidhu/passport-photo-app.git
echo ========================================================
cd /d "%~dp0"
git push -u origin main
if errorlevel 1 (
    echo.
    echo [NOTE] If a browser window opened, please click 'Sign in' / 'Authorize'.
    echo If the repository does not exist yet on GitHub, please create it at:
    echo https://github.com/new (Name: passport-photo-app)
) else (
    echo.
    echo ========================================================
    echo [SUCCESS] Code successfully pushed to GitHub!
    echo View at: https://github.com/urfavsidhu/passport-photo-app
    echo ========================================================
)
pause
