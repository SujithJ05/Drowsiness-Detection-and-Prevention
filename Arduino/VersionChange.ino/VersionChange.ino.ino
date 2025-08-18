// Define motor control pins
const int motorPin1 = 9;    // Motor control pin 1 (PWM)
const int motorPin2 = 10;   // Motor control pin 2 (PWM)
const int enablePin = 11;
int motorSpeed = 200;  // Initial motor speed (0 to 255)
const int stopTime = 2000;  // Total deceleration time (2 sec)
const int steps = 100;      // Number of steps for smooth braking
int delayTime = stopTime / steps;// Enable pin for motor driver

// Variables
String command = "";        
bool braking = false;       
bool warning = false;       
unsigned long warningStartTime = 0;  // Time when warning started
const unsigned long WARNING_TIMEOUT = 5000;  // 5 seconds timeout

void setup() {
  Serial.begin(9600);

  pinMode(motorPin1, OUTPUT);
  pinMode(motorPin2, OUTPUT);
  pinMode(enablePin, OUTPUT);

  // Start motor running
  digitalWrite(enablePin, HIGH);
  analogWrite(motorPin1, 200);
  digitalWrite(motorPin2, LOW);

  Serial.println("System Ready: Motor running...");
}

void loop() {
  if (Serial.available() > 0) {
    command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command == "WARNING") {
      activateWarning();
    } 
    else if (command == "RELEASE") {
      releaseBrakes();
    }
  }

  // Check if warning timeout (5 sec) has passed
  if (warning && !braking) {
    if (millis() - warningStartTime >= WARNING_TIMEOUT) {
      applyBrakes();
    }
  }
}

void activateWarning() {
  if (!warning && !braking) {
    Serial.println("WARNING: Drowsiness detected! Respond within 5 seconds.");
    warning = true;
    warningStartTime = millis();  // Start 5-sec timer
  }
}


void applyBrakes() {
  if (!braking) {
    Serial.println("EMERGENCY: No response detected. Braking activated.");

    // Gradual braking logic
    for (int i = 0; i < steps; i++) {
      motorSpeed -= motorSpeed / steps; // Reduce speed smoothly
      if (motorSpeed < 0) motorSpeed = 0;
      analogWrite(motorPin1, motorSpeed);
      delay(delayTime); // Smooth transition
    }

    // Ensure full stop
    digitalWrite(enablePin, LOW);
    digitalWrite(motorPin1, LOW);
    digitalWrite(motorPin2, LOW);

    braking = true;
    warning = false;
  }
}

void releaseBrakes() {
  if (braking) {
    Serial.println("Brakes released. Motor running again.");

    digitalWrite(enablePin, HIGH);
    analogWrite(motorPin1, 200);
    digitalWrite(motorPin2, LOW);

    braking = false;
  }
}
