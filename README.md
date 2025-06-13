![PXL_20250613_173300470](https://github.com/user-attachments/assets/e99de2a8-19c7-4b9f-a44d-c2b9f704f7eb)
# FocusMaxxer Candy Dispenser 🍬

Arduino-based productivity tool that rewards focused work with candy. Uses AI to detect distractions and RGB eyes to show mood.

## What it does
- Monitor computer activity during focus sessions
- Dispense candy for successful sessions
- Progressive punishments for distractions (session extensions, candy locks, parent emails)
- RGB eyes change color: white (idle) → green (focused) → red (distracted/locked)

## Dependencies

### Arduino (`main.cpp`)
```cpp
#include <LiquidCrystal.h>
#include <Servo.h>
```

### Python (`main.py`)
```bash
pip install pygetwindow keyboard requests pyserial python-dotenv
```

### Environment File (`.env`)
```
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
PARENT_EMAIL=parent@gmail.com
API_ENDPOINT=your_ai_api_endpoint
```

## How to Use
1. Upload `main.cpp` to Arduino
2. Run `main.py` on computer
3. Set focus time with UP/DOWN buttons (default: 20 seconds)
4. Press ENTER to start session
5. Stay focused - avoid distracting websites/apps
6. Complete session → get candy! 🍬

Built by Naman Sonawane & Deming Chen
