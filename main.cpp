#include <LiquidCrystal.h>
#include <Servo.h>

LiquidCrystal lcd(12, 11, 5, 4, 3, 2);
Servo candyServo;


const int btnUp = 7;
const int btnDown = 6;
const int btnEnter = 8; 
const int servoPin = 9;
const int buzzerPin = A0;

// RGB LED pins for both "eyes" (wired in parallel)
const int eyesRedPin = A1;
const int eyesGreenPin = A2;
const int eyesBluePin = A3;

int focusTime = 20;
bool inSession = false;
bool isLocked = false;
bool candyLocked = false;
bool eyesRed = false;
unsigned long sessionStart;
unsigned long lockStart;
unsigned long candyLockStart;
unsigned long countdownTime;
unsigned long eyesRedStart;
bool waitingForResult = false;
const unsigned long LOCK_DURATION = 30000;
const unsigned long EYES_RED_DURATION = 3000; // 3 seconds
unsigned long candyLockDuration = 0;

void setup() {
  Serial.begin(9600);
  lcd.begin(16, 2);
  pinMode(btnUp, INPUT_PULLUP);
  pinMode(btnDown, INPUT_PULLUP);
  pinMode(btnEnter, INPUT_PULLUP);
  pinMode(buzzerPin, OUTPUT);

  // Initialize RGB LED pins
  pinMode(eyesRedPin, OUTPUT);
  pinMode(eyesGreenPin, OUTPUT);
  pinMode(eyesBluePin, OUTPUT);

  candyServo.attach(servoPin);
  candyServo.write(30);
  
  // Set initial eye color to white
  setEyeColor(255, 255, 255);
  
  Serial.println("Arduino initialized");
  Serial.println("LCD initialized");
  Serial.println("Ready for commands");
  
  updateTimeDisplay();
}

void loop() {
  if (Serial.available()) {
    String message = Serial.readStringUntil('\n');
    message.trim();
    Serial.println("Received: " + message);
    
    if (message == "buzzer") {
      playWarningBuzzer();
      // Turn eyes red for 3 seconds when distraction detected
      setEyeColor(255, 0, 0); // Red
      eyesRed = true;
      eyesRedStart = millis();
    }
    else if (message == "heartbeat") {
      Serial.println("heartbeat_ok");
    }
    else if (message.startsWith("distraction_")) {
      handleDistractionDisplay(message);
    }
    else if (message == "extend_10") {
      extendSession(10);
    }
    else if (message == "extend_20") {
      extendSession(20);
    }
    else if (message == "candy_lock_10") {
      lockCandy(10 * 60 * 1000UL);
    }
    else if (message == "candy_lock_20") {
      lockCandy(20 * 60 * 1000UL);
    }
    else if (message == "end_session") {
      endSessionImmediately();
    }
    else if (message.startsWith("summary_")) {
      int distractionCount = message.substring(8).toInt();
      showSummary(distractionCount);
    }
    else if (message == "lock") {
      Serial.println("IMMEDIATE LOCK activated!");
      activateLock();
    }
    else if (waitingForResult) {
      if (message == "success") {
        Serial.println("Success received!");
        
        // Play happy completion sound
        playHappySound();
        
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("Great job!");
        lcd.setCursor(0, 1);
        lcd.print("Candy earned!");
        delay(2000);
        
        if (candyLocked) {
          lcd.clear();
          lcd.setCursor(0, 0);
          lcd.print("Candy is locked!");
          lcd.setCursor(0, 1);
          unsigned long remaining = (candyLockDuration - (millis() - candyLockStart)) / 1000;
          lcd.print("Wait ");
          lcd.print(remaining/60);
          lcd.print("m ");
          lcd.print(remaining%60);
          lcd.print("s");
          delay(2000);
        } else {
          dispenseCandy();
        }
        
        // Return eyes to white after completion
        setEyeColor(255, 255, 255);
      } else if (message == "fail") {
        Serial.println("Fail received!");
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("Session failed!");
        lcd.setCursor(0, 1);
        lcd.print("Try again later");
        delay(2000);
        
        // Return eyes to white after failure
        setEyeColor(255, 255, 255);
        updateTimeDisplay();
      }
      waitingForResult = false;
    }
  }

  // Handle temporary red eyes (3 second duration)
  if (eyesRed && !candyLocked && (millis() - eyesRedStart >= EYES_RED_DURATION)) {
    eyesRed = false;
    if (inSession) {
      setEyeColor(0, 255, 0); // Return to green during session
    } else {
      setEyeColor(255, 255, 255); // Return to white when not in session
    }
  }

  if (isLocked) {
    unsigned long lockElapsed = millis() - lockStart;
    if (lockElapsed >= LOCK_DURATION) {
      isLocked = false;
      inSession = false;
      Serial.println("Lock period ended");
      setEyeColor(255, 255, 255); // White when unlocked
      updateTimeDisplay();
    } else {
      displayLockCountdown(LOCK_DURATION - lockElapsed);
    }
    return;
  }

  if (candyLocked) {
    unsigned long candyLockElapsed = millis() - candyLockStart;
    if (candyLockElapsed >= candyLockDuration) {
      candyLocked = false;
      Serial.println("Candy lock period ended");
      // Return to appropriate eye color based on session state
      if (inSession) {
        setEyeColor(0, 255, 0); // Green during session
      } else {
        setEyeColor(255, 255, 255); // White when idle
      }
    }
  }

  if (!inSession && !waitingForResult && !isLocked) {
    if (digitalRead(btnUp) == LOW) {
      focusTime += 5;
      if (focusTime > 3600) focusTime = 3600; // Max 1 hour
      Serial.println("Time increased to: " + String(focusTime));
      updateTimeDisplay();
      delay(200);
    }
    if (digitalRead(btnDown) == LOW && focusTime > 5) {
      focusTime -= 5;
      Serial.println("Time decreased to: " + String(focusTime));
      updateTimeDisplay();
      delay(200);
    }
    if (digitalRead(btnEnter) == LOW) {
      Serial.println("Enter pressed - starting session");
      startCountdown();
      delay(200);
    }
  }

  if (inSession && !isLocked) {
    unsigned long elapsed = millis() - sessionStart;
    
    if (elapsed >= countdownTime) {
      Serial.println("Session completed! Sending 'done'");
      inSession = false;
      waitingForResult = true;
      Serial.println("done");
      
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Session Done!");
      lcd.setCursor(0, 1);
      lcd.print("Checking...");
    } else {
      unsigned long remaining = countdownTime - elapsed;
      displayCountdown(remaining);
      
      static unsigned long lastDebugTime = 0;
      if (millis() - lastDebugTime > 10000) {
        Serial.println("Time remaining: " + String(remaining/1000) + " seconds");
        lastDebugTime = millis();
      }
    }
  }
}

// Function to set eye color (0-255 for each color)
void setEyeColor(int red, int green, int blue) {
  analogWrite(eyesRedPin, red);
  analogWrite(eyesGreenPin, green);
  analogWrite(eyesBluePin, blue);
}

// Play happy completion sound
void playHappySound() {
  // Happy melody - ascending notes
  int happyMelody[] = {262, 294, 330, 349, 392, 440, 494, 523}; // C4 to C5 scale
  int noteDurations[] = {200, 200, 200, 200, 300, 300, 400, 600};
  
  for (int i = 0; i < 8; i++) {
    tone(buzzerPin, happyMelody[i], noteDurations[i]);
    delay(noteDurations[i]);
    noTone(buzzerPin);
    delay(50); // Short pause between notes
  }
}

void handleDistractionDisplay(String message) {
  int firstUnderscore = message.indexOf('_');
  int secondUnderscore = message.indexOf('_', firstUnderscore + 1);
  
  if (firstUnderscore != -1 && secondUnderscore != -1) {
    int count = message.substring(firstUnderscore + 1, secondUnderscore).toInt();
    String site = message.substring(secondUnderscore + 1);
    
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Distraction #");
    lcd.print(count);
    lcd.setCursor(0, 1);
    if (site.length() > 16) {
      site = site.substring(0, 16);
    }
    lcd.print(site);
    delay(1000);
    
    Serial.println("Displayed distraction: " + site);
  }
}

void playWarningBuzzer() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(buzzerPin, HIGH);
    delay(200);
    digitalWrite(buzzerPin, LOW);
    delay(100);
  }
  Serial.println("Warning buzzer played");
}

void extendSession(int minutes) {
  if (inSession) {
    unsigned long extensionTime = minutes * 60UL * 1000UL;
    countdownTime += extensionTime;
    
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Session Extended");
    lcd.setCursor(0, 1);
    lcd.print("+" + String(minutes) + " minutes!");
    delay(1000);
    
    Serial.println("Session extended by " + String(minutes) + " minutes");
  }
}

void lockCandy(unsigned long duration) {
  candyLocked = true;
  candyLockStart = millis();
  candyLockDuration = duration;
  
  // Set eyes to red when candy is locked
  setEyeColor(255, 0, 0);
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Candy Locked!");
  lcd.setCursor(0, 1);
  lcd.print("For " + String(duration/60000) + " minutes");
  delay(1000);
  
  Serial.println("Candy locked for " + String(duration/60000) + " minutes");
}

void endSessionImmediately() {
  if (inSession) {
    inSession = false;
    waitingForResult = true;
    
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Session Ended!");
    lcd.setCursor(0, 1);
    lcd.print("Too many strikes");
    delay(2000);
    
    Serial.println("Session ended due to excessive distractions");
    Serial.println("done");
  }
}

void showSummary(int distractionCount) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Session Summary:");
  lcd.setCursor(0, 1);
  lcd.print("Distractions: ");
  lcd.print(distractionCount);
  delay(2000);
  
  Serial.println("Summary displayed: " + String(distractionCount) + " distractions");
}

void activateLock() {
  isLocked = true;
  inSession = false;
  lockStart = millis();
  
  Serial.println("LOCKED for " + String(LOCK_DURATION/1000) + " seconds");
}

void displayLockCountdown(unsigned long ms) {
  int sec = ms / 1000;
  
  static bool flashState = false;
  static unsigned long lastFlash = 0;
  static int lastDisplayedSec = -1;
  static bool lastFlashState = false;
  
  if (millis() - lastFlash > 500) {
    flashState = !flashState;
    lastFlash = millis();
  }
  
  if (flashState != lastFlashState || sec != lastDisplayedSec) {
    lcd.clear();
    
    if (flashState) {
      lcd.setCursor(0, 0);
      lcd.print("*** LOCKED ***");
      lcd.setCursor(0, 1);
      lcd.print("Unlock in: ");
      lcd.print(sec);
      lcd.print("s   ");
    }
    
    lastFlashState = flashState;
    lastDisplayedSec = sec;
  }
}

void updateTimeDisplay() {
  Serial.println("Updating time display: " + String(focusTime));
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Set Time:");
  lcd.setCursor(0, 1);
  lcd.print(focusTime);
  lcd.print(" sec");
  
  if (candyLocked) {
    delay(1000);
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Candy Locked!");
    lcd.setCursor(0, 1);
    unsigned long remaining = (candyLockDuration - (millis() - candyLockStart)) / 1000;
    lcd.print(remaining/60);
    lcd.print("m ");
    lcd.print(remaining%60);
    lcd.print("s left");
    delay(2000);
    
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Set Time:");
    lcd.setCursor(0, 1);
    lcd.print(focusTime);
    lcd.print(" sec");
  }
}

void startCountdown() {
  Serial.println("Starting countdown for " + String(focusTime) + " seconds");
  countdownTime = focusTime * 1000UL; // Convert seconds to milliseconds
  sessionStart = millis();
  inSession = true;
  
  // Set eyes to green when focus session starts
  setEyeColor(0, 255, 0);
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Focus Session");
  lcd.setCursor(0, 1);
  lcd.print("Starting...");
  delay(2000);
}

void displayCountdown(unsigned long ms) {
  int min = (ms / 1000) / 60;
  int sec = (ms / 1000) % 60;
  
  static int lastMin = -1;
  static int lastSec = -1;
  
  if (min != lastMin || sec != lastSec) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Focus Time:");
    lcd.setCursor(0, 1);
    if (min < 10) lcd.print(" ");
    lcd.print(min);
    lcd.print("m ");
    if (sec < 10) lcd.print("0");
    lcd.print(sec);
    lcd.print("s");
    
    lastMin = min;
    lastSec = sec;
  }
}

void dispenseCandy() {
  Serial.println("Dispensing candy!");
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Dispensing...");
  lcd.setCursor(0, 1);
  lcd.print("Enjoy! :)");
  
  candyServo.write(30);
  delay(500);
  candyServo.write(90);
  delay(500);
  candyServo.write(30);
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Candy Dispensed!");
  lcd.setCursor(0, 1);
  lcd.print("Well done!");
  delay(2000);
  
  updateTimeDisplay();
}