@echo off
setlocal EnableDelayedExpansion

echo Checking Windows version for NovaExternalCS2.py compatibility...
echo Please specify your Windows version.
set /p WIN_VERSION=Enter your Windows version (e.g., 10 or 11): 
if "!WIN_VERSION!"=="10" (
    echo Windows 10 detected. Proceeding with installation...
) else if "!WIN_VERSION!"=="11" (
    echo Windows 11 detected. Proceeding with installation...
) else (
    echo Warning: NovaExternalCS2.py is designed for Windows 10 or 11. You entered Windows !WIN_VERSION!, which may not be fully compatible.
    set /p CONTINUE=Continue with installation anyway? (y/n): 
    if /i "!CONTINUE!" NEQ "y" (
        echo Installation aborted.
        pause
        exit /b 1
    )
    echo Proceeding with installation on Windows !WIN_VERSION!...


echo off
setlocal EnableDelayedExpansion

echo Installing Python 3.10.8 and dependencies for Nova...

:: Set variables
set PYTHON_VERSION=3.10.8
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe
set PYTHON_INSTALLER=python-installer.exe
set PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python310
set PIP_URL=https://bootstrap.pypa.io/get-pip.py
set PIP_INSTALLER=get-pip.py
set ARDUINO_SKETCH=NovaCS2Arduino.ino
set ARDUINO_SKETCH_URL=https://raw.githubusercontent.com/a2x/cs2-dumper/main/arduino/NovaCS2Arduino.ino


net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo This script requires administrative privileges. Please run as Administrator.
    pause
    exit /b 1
)


echo Checking for Python %PYTHON_VERSION%...
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "tokens=2 delims= " %%i in ('python --version 2^>nul') do set CURRENT_PY_VERSION=%%i
    if "!CURRENT_PY_VERSION!"=="%PYTHON_VERSION%" (
        echo Python %PYTHON_VERSION% is already installed.
    ) else (
        echo Found Python !CURRENT_PY_VERSION!, but %PYTHON_VERSION% is required. Installing...
        goto InstallPython
    )
) else (
    echo Python is not installed. Installing Python %PYTHON_VERSION%...
    goto InstallPython
)

:InstallPython

echo Downloading Python %PYTHON_VERSION%...
powershell -Command "Invoke-WebRequest -Uri %PYTHON_URL% -OutFile %PYTHON_INSTALLER%"
if not exist %PYTHON_INSTALLER% (
    echo Failed to download Python installer.
    pause
    exit /b 1
)

:: Install Python silently
echo Installing Python %PYTHON_VERSION%...
%PYTHON_INSTALLER% /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
if %ERRORLEVEL% neq 0 (
    echo Failed to install Python.
    del %PYTHON_INSTALLER%
    pause
    exit /b 1
)
del %PYTHON_INSTALLER%

:: Verify Python installation
echo Verifying Python installation...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python installation verification failed.
    pause
    exit /b 1
)
python --version | findstr %PYTHON_VERSION% >nul
if %ERRORLEVEL% neq 0 (
    echo Python %PYTHON_VERSION% was not installed correctly.
    pause
    exit /b 1
)
echo Python %PYTHON_VERSION% installed successfully.

:: Ensure pip is installed
echo Ensuring pip is installed...
powershell -Command "Invoke-WebRequest -Uri %PIP_URL% -OutFile %PIP_INSTALLER%"
if not exist %PIP_INSTALLER% (
    echo Failed to download pip installer.
    pause
    exit /b 1
)
python %PIP_INSTALLER%
if %ERRORLEVEL% neq 0 (
    echo Failed to install pip.
    del %PIP_INSTALLER%
    pause
    exit /b 1
)
del %PIP_INSTALLER%

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
if %ERRORLEVEL% neq 0 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

:: Install required Python packages
echo Installing required Python packages...
python -m pip install dearpygui pyMeow pypresence psutil requests pywin32 pyserial
if %ERRORLEVEL% neq 0 (
    echo Failed to install one or more Python packages.
    pause
    exit /b 1
)

:: Arduino Setup
echo.
echo Arduino Setup
echo -------------
echo NovaExternalCS2.py supports Arduino for mouse control (e.g., aimbot, triggerbot).
echo This requires an Arduino board with USB HID support (e.g., Arduino Leonardo, Micro).
set /p USE_ARDUINO=Would you like to set up Arduino support now? (y/n): 
if /i "!USE_ARDUINO!"=="y" (
    echo.
    echo Available COM ports:
    powershell -Command "Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description | Format-Table -AutoSize"
    set /p COM_PORT=Enter the COM port for your Arduino (e.g., COM3): 
    if "!COM_PORT!"=="" (
        echo No COM port specified. Skipping Arduino setup.
        goto EndArduinoSetup
    )

    :: Create Arduino sketch
    echo Creating Arduino sketch...
    (
        echo // NovaCS2Arduino.ino
        echo // Compatible with NovaExternalCS2.py for mouse control
        echo #include ^<Mouse.h^>
        echo.
        echo void setup() {
        echo   Serial.begin(9600);
        echo   Mouse.begin();
        echo   // Wait for Serial to initialize
        echo   while (!Serial) {
        echo     delay(10);
        echo   }
        echo }
        echo.
        echo void loop() {
        echo   if (Serial.available() ^> 0) {
        echo     String command = Serial.readStringUntil('\n');
        echo     command.trim();
        echo     if (command.startsWith("MOVE")) {
        echo       int spaceIndex = command.indexOf(' ', 5);
        echo       int dx = command.substring(5, spaceIndex).toInt();
        echo       int dy = command.substring(spaceIndex + 1).toInt();
        echo       Mouse.move(dx, dy, 0);
        echo     } else if (command.startsWith("CLICK")) {
        echo       String state = command.substring(6);
        echo       if (state == "DOWN") {
        echo         Mouse.press(MOUSE_LEFT);
        echo       } else if (state == "UP") {
        echo         Mouse.release(MOUSE_LEFT);
        echo       }
        echo     }
        echo   }
        echo }
    ) > %ARDUINO_SKETCH%
    if %ERRORLEVEL% neq 0 (
        echo Failed to create Arduino sketch.
        pause
        exit /b 1
    )
    echo Arduino sketch created: %ARDUINO_SKETCH%

    :: Check for Arduino IDE
    echo Checking for Arduino IDE...
    set ARDUINO_IDE=
    for %%i in (arduino.exe) do (
        set ARDUINO_IDE=%%~$PATH:i
    )
    if "!ARDUINO_IDE!"=="" (
        echo Arduino IDE not found in PATH.
        echo Please manually upload %ARDUINO_SKETCH% to your Arduino using the Arduino IDE.
        echo Download the Arduino IDE from: https://www.arduino.cc/en/software
        echo Ensure your Arduino is connected to !COM_PORT! and supports USB HID (e.g., Leonardo, Micro).
        echo After uploading the sketch, enable Arduino in NovaExternalCS2.py GUI and select !COM_PORT!.
    ) else (
        echo Arduino IDE found: !ARDUINO_IDE!
        echo Attempting to upload %ARDUINO_SKETCH% to !COM_PORT!...
        "!ARDUINO_IDE!" --upload --port !COM_PORT! %ARDUINO_SKETCH%
        if %ERRORLEVEL% neq 0 (
            echo Failed to upload Arduino sketch. Please upload %ARDUINO_SKETCH% manually using the Arduino IDE.
            echo Ensure your Arduino is connected to !COM_PORT! and supports USB HID.
        ) else (
            echo Arduino sketch uploaded successfully to !COM_PORT!.
            echo Enable Arduino in NovaExternalCS2.py GUI and select !COM_PORT!.
        )
    )
) else (
    echo Skipping Arduino setup.
)

:EndArduinoSetup
echo.
echo Installation and setup completed successfully!
echo You can now run NovaExternalCS2.py.
pause
exit /b 0