// SOTA Driver Safety System - Arduino Controller
// Features: Heartbeat Safety, Gradual Braking, Status Telemetry

#if __has_include(<Arduino.h>)
#include <Arduino.h>
#else
#include <cstdint>

#define OUTPUT 0x1
#define HIGH 0x1
#define LOW 0x0

class String {
public:
  void trim();
  bool operator==(const char* rhs) const;
};

class SerialMock {
public:
  void begin(long baud);
  int available();
  String readStringUntil(char terminator);
  void println(const char* message);
};

extern SerialMock Serial;

unsigned long millis();
void delay(unsigned long ms);
void pinMode(int pin, int mode);
void digitalWrite(int pin, int value);
void analogWrite(int pin, int value);
#endif

const int motorPin1 = 9;    
const int enablePin = 11;   
const int normalLED = 5;    
const int warningLED = 6;   
const int brakingLED = 7;   
const int buzzerPin = 4;    

// Safety Settings
unsigned long lastHeartbeat = 0;
const unsigned long HEARTBEAT_TIMEOUT = 2000; // 2 seconds safety window

bool brakingActive = false;
bool warningActive = false;
int currentSpeed = 200;

void setup() {
  Serial.begin(9600);
  pinMode(motorPin1, OUTPUT);
  pinMode(enablePin, OUTPUT);
  pinMode(normalLED, OUTPUT);
  pinMode(warningLED, OUTPUT);
  pinMode(brakingLED, OUTPUT);
  pinMode(buzzerPin, OUTPUT);

  // Initial State: Safe/Running
  digitalWrite(enablePin, HIGH);
  analogWrite(motorPin1, currentSpeed);
  digitalWrite(normalLED, HIGH);
  lastHeartbeat = millis();
  
  Serial.println("ARDUINO_SYSTEM_ONLINE");
}

void loop() {
  // 1. Check Safety Heartbeat
  if (millis() - lastHeartbeat > HEARTBEAT_TIMEOUT) {
    enterSafeState();
  }

  // 2. Process Commands
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "HEARTBEAT") {
      lastHeartbeat = millis();
    } 
    else if (cmd == "BRAKE") {
      applyBrakes();
    } 
    else if (cmd == "RELEASE") {
      releaseBrakes();
    } 
    else if (cmd == "WARNING") {
      activateWarning();
    }
  }

  // 3. Visual Feedback Logic
  handleFeedback();
}

void applyBrakes() {
  if (!brakingActive) {
    brakingActive = true;
    warningActive = false;
    // Gradual deceleration
    for (int s = currentSpeed; s >= 0; s -= 5) {
      analogWrite(motorPin1, s);
      delay(10);
    }
    digitalWrite(enablePin, LOW);
    Serial.println("BRAKE_CONFIRMED");
  }
}

void releaseBrakes() {
  brakingActive = false;
  warningActive = false;
  digitalWrite(enablePin, HIGH);
  analogWrite(motorPin1, currentSpeed);
  Serial.println("RELEASE_CONFIRMED");
}

void activateWarning() {
  if (!brakingActive) {
    warningActive = true;
    Serial.println("WARNING_CONFIRMED");
  }
}

void enterSafeState() {
  // If we lose connection, release brakes but pulse warning LED
  // (Don't lock brakes on highway due to computer crash!)
  if (brakingActive) releaseBrakes();
  digitalWrite(warningLED, (millis() / 500) % 2);
}

void handleFeedback() {
  if (brakingActive) {
    digitalWrite(brakingLED, HIGH);
    digitalWrite(normalLED, LOW);
    digitalWrite(warningLED, LOW);
    if ((millis() / 200) % 2) digitalWrite(buzzerPin, HIGH);
    else digitalWrite(buzzerPin, LOW);
  } else if (warningActive) {
    digitalWrite(brakingLED, LOW);
    digitalWrite(normalLED, LOW);
    digitalWrite(warningLED, HIGH);
    if ((millis() / 1000) % 2) digitalWrite(buzzerPin, HIGH);
    else digitalWrite(buzzerPin, LOW);
  } else {
    digitalWrite(brakingLED, LOW);
    digitalWrite(normalLED, HIGH);
    digitalWrite(warningLED, LOW);
    digitalWrite(buzzerPin, LOW);
  }
}
