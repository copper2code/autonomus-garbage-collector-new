#include <ArduinoJson.h>
#include <Servo.h>

// ------------------------------------------------------------------
// PINS CONFIGURATION
// ------------------------------------------------------------------
// Base Stepper
const int BASE_PINS[4] = {2, 3, 4, 5};
// Joint Stepper
const int JOINT_PINS[4] = {6, 7, 8, 9};
// Extension Stepper
const int EXT_PINS[4] = {10, 11, 12, 13};

// Clamp Servo
const int SERVO_PIN = A0;

Servo clampServo;

// ULN2003 half-step sequence
const int stepsMatrix[8][4] = {
  {1, 0, 0, 0},
  {1, 1, 0, 0},
  {0, 1, 0, 0},
  {0, 1, 1, 0},
  {0, 0, 1, 0},
  {0, 0, 1, 1},
  {0, 0, 0, 1},
  {1, 0, 0, 1}
};

const int stepDelay = 3; // ms delay between steps

void setup() {
  Serial.begin(115200);

  // Initialize Stepper Pins
  for (int i = 0; i < 4; i++) {
    pinMode(BASE_PINS[i], OUTPUT);
    pinMode(JOINT_PINS[i], OUTPUT);
    pinMode(EXT_PINS[i], OUTPUT);
  }
  
  // Disable coils initially to prevent heating
  disableCoils(BASE_PINS);
  disableCoils(JOINT_PINS);
  disableCoils(EXT_PINS);

  // Initialize Servo
  clampServo.attach(SERVO_PIN);
  clampServo.write(10); // Start open
}

void loop() {
  if (Serial.available() > 0) {
    String jsonStr = Serial.readStringUntil('\n');
    
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, jsonStr);
    
    if (error) {
      Serial.println(F("{\"status\": \"error\", \"msg\": \"invalid json\"}"));
      return;
    }
    
    const char* cmd = doc["cmd"];
    
    if (strcmp(cmd, "arm") == 0) {
      const char* motor = doc["motor"];
      int steps = doc["steps"];
      int dir = doc["dir"]; // 1 forward, 0 backward
      
      const int* targetPins = NULL;
      
      if (strcmp(motor, "base") == 0) targetPins = BASE_PINS;
      else if (strcmp(motor, "joint") == 0) targetPins = JOINT_PINS;
      else if (strcmp(motor, "ext") == 0) targetPins = EXT_PINS;
      
      if (targetPins != NULL) {
        moveStepper(targetPins, steps, dir);
        Serial.println(F("{\"status\": \"ok\"}"));
      } else {
        Serial.println(F("{\"status\": \"error\", \"msg\": \"unknown motor\"}"));
      }
      
    } else if (strcmp(cmd, "clamp") == 0) {
      int angle = doc["angle"];
      clampServo.write(angle);
      // Let the servo physically move
      delay(300); 
      Serial.println(F("{\"status\": \"ok\"}"));
    }
  }
}

void moveStepper(const int* motorPins, int totalSteps, int dir) {
  int stepIndex = 0;
  for (int i = 0; i < totalSteps; i++) {
    for (int pin = 0; pin < 4; pin++) {
      digitalWrite(motorPins[pin], stepsMatrix[stepIndex][pin]);
    }
    
    delay(stepDelay);
    
    if (dir == 1) {
      stepIndex++;
      if (stepIndex > 7) stepIndex = 0;
    } else {
      stepIndex--;
      if (stepIndex < 0) stepIndex = 7;
    }
  }
  
  // Power off coils when idle to prevent overheating 28BYJ-48
  disableCoils(motorPins);
}

void disableCoils(const int* motorPins) {
  for (int pin = 0; pin < 4; pin++) {
    digitalWrite(motorPins[pin], LOW);
  }
}
