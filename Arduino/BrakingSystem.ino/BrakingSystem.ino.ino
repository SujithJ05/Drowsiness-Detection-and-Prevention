// Arduino code for drowsiness detection emergency braking system
// Uses a DC motor to simulate braking mechanism

// Define pins
const int motorPin1 = 9;    // Motor control pin 1 (PWM)
const int motorPin2 = 10;   // Motor control pin 2 (PWM)
const int enablePin = 11;   // Enable pin for motor driver
const int normalLED = 5;    // Green LED for normal operation
const int warningLED = 6;   // Yellow LED for warning state
const int brakingLED = 7;   // Red LED for active braking
const int buzzerPin = 4;    // Buzzer for audible warnings

// Variables
String command = "";        // To store incoming commands
bool braking = false;       // Tracks if braking is currently active
bool warning = false;       // Tracks if warning is active
unsigned long brakeStartTime = 0; // Time when braking started
unsigned long lastCommandTime = 0; // Time of last received command
int brakeStrength = 255;    // PWM value for braking (0-255)
const unsigned long COMM_TIMEOUT = 10000; // Communication timeout (10 seconds)

void setup() {
  // [existing setup code]
  
  // Start the motor running by default
  digitalWrite(enablePin, HIGH);   // Enable motor driver
  analogWrite(motorPin1, 200);     // Set default speed (adjust as needed)
  digitalWrite(motorPin2, LOW);    // Direction control
  
  Serial.println("Arduino emergency braking system ready - Motor running");
  // [rest of setup]
}

void loop() {
  // Check if data is available
  if (Serial.available() > 0) {
    // Read incoming command
    command = Serial.readStringUntil('\n');
    command.trim();  // Remove any whitespace
    lastCommandTime = millis(); // Update command time
    
    // Process command
    if (command == "BRAKE") {
      applyBrakes();
    } 
    else if (command == "RELEASE") {
      releaseBrakes();
    }
    else if (command == "WARNING") {
      activateWarning();
    }
    else if (command == "STATUS") {
      // Report status back to Python
      reportStatus();
    }
  }
  
  // If braking is active, maintain brake pressure and blink LED
  if (braking) {
    unsigned long currentTime = millis();
    // Blink the brake LED quickly (200ms on/off)
    if ((currentTime - brakeStartTime) % 400 < 200) {
      digitalWrite(brakingLED, HIGH);
    } else {
      digitalWrite(brakingLED, LOW);
    }
    
    // Beep buzzer during braking
    if ((currentTime - brakeStartTime) % 800 < 200) {
      digitalWrite(buzzerPin, HIGH);
    } else {
      digitalWrite(buzzerPin, LOW);
    }
  }
  
  // If warning is active, blink warning LED
  if (warning && !braking) {
    unsigned long currentTime = millis();
    // Blink the warning LED slowly (500ms on/off)
    if ((currentTime / 500) % 2 == 0) {
      digitalWrite(warningLED, HIGH);
    } else {
      digitalWrite(warningLED, LOW);
    }
    
    // Occasional beep
    if ((currentTime / 2000) % 2 == 0 && (currentTime % 2000) < 100) {
      digitalWrite(buzzerPin, HIGH);
    } else {
      digitalWrite(buzzerPin, LOW);
    }
  }
  
  // Safety feature: If communication is lost for too long while in warning mode, 
  // automatically release brakes and return to normal
  if ((millis() - lastCommandTime > COMM_TIMEOUT) && (braking || warning)) {
    Serial.println("COMMUNICATION TIMEOUT: Releasing brakes for safety");
    releaseBrakes();
  }
}


void applyBrakes() {
  // Stop the motor when drowsiness detected
  if (!braking) {
    Serial.println("EMERGENCY: Auto-braking activated");
    
    // Turn off normal and warning LEDs
    digitalWrite(normalLED, LOW);
    digitalWrite(warningLED, LOW);
    
    // Turn on braking LED
    digitalWrite(brakingLED, HIGH);
    
    // Stop the motor (CHANGED FROM ORIGINAL)
    digitalWrite(enablePin, LOW);  // Disable motor driver
    digitalWrite(motorPin1, LOW);  // Stop motor
    digitalWrite(motorPin2, LOW);  // Stop motor
    
    // Store the time when braking started
    brakeStartTime = millis();
    
    // Update status flags
    braking = true;
    warning = false;
    
    // Send feedback to serial (for Python script)
    Serial.println("BRAKE_ACKNOWLEDGED");
  }
}

void releaseBrakes() {
  // Resume motor operation when alert cleared
  if (braking || warning) {
    Serial.println("Auto-braking released - resuming motor");
    
    // Turn off braking and warning LEDs
    digitalWrite(brakingLED, LOW);
    digitalWrite(warningLED, LOW);
    digitalWrite(buzzerPin, LOW);
    
    // Turn on normal operation LED
    digitalWrite(normalLED, HIGH);
    
    // Restart the motor (CHANGED FROM ORIGINAL)
    digitalWrite(enablePin, HIGH);   // Enable motor driver
    analogWrite(motorPin1, 200);     // Resume motor operation (adjust speed as needed)
    digitalWrite(motorPin2, LOW);    // Direction control
    
    // Update status flags
    braking = false;
    warning = false;
    
    // Send feedback to serial (for Python script)
    Serial.println("RELEASE_ACKNOWLEDGED");
  }
}
void activateWarning() {
  // Activate warning state (before applying brakes)
  if (!warning && !braking) {
    Serial.println("WARNING: Drowsiness detected! Driver needs to respond");
    
    // Turn on warning LED
    digitalWrite(warningLED, HIGH);
    
    // Keep normal LED on but dimmer
    analogWrite(normalLED, 50);  // Reduced brightness
    
    // Short warning beep
    digitalWrite(buzzerPin, HIGH);
    delay(100);
    digitalWrite(buzzerPin, LOW);
    
    // Update status flag
    warning = true;
    
    // Send feedback to serial (for Python script)
    Serial.println("WARNING_ACKNOWLEDGED");
  }
}

void reportStatus() {
  // Report current system status back to Python
  if (braking) {
    Serial.println("STATUS:BRAKING");
  } else if (warning) {
    Serial.println("STATUS:WARNING");
  } else {
    Serial.println("STATUS:NORMAL");
  }
}