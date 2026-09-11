@echo off
echo =========================================================================
echo Launching Google Chrome with Dedicated Naukri Automation Profile
echo =========================================================================
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\sriha\AppData\Local\Google\Chrome\NaukriAutomation" --profile-directory="Profile 18" --remote-allow-origins=* "https://resdex.naukri.com/v3?activeTab=advSrch"
echo Chrome Automation Profile opened with Naukri Resdex on port 9222.
