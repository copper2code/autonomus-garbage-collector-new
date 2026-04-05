#include <ArduinoJson.h>
#include <Servo.h>

// ---------------- PIN CONFIG ----------------
const int BASE_PINS[4]  = {2, 3, 4, 5};
const int JOINT_PINS[4] = {6, 7, 8, 9};
const int EXT_PINS[4]   = {10, 11, 12, 13};

const int SERVO_PIN = A0;

Servo clampServo;

// ---------------- STEPPER STATE ----------------
struct StepperState {
  const int* pins;
  int stepIndex;
  int stepsRemaining;
  int dir;
  unsigned long lastStepTime;
  int stepDelay;
};

StepperState base  = {BASE_PINS, 0, 0, 1, 0, 3};
StepperState joint = {JOINT_PINS, 0, 0, 1, 0, 3};
StepperState ext   = {EXT_PINS, 0, 0, 1, 0, 3};

// Half-step sequence
const int stepsMatrix[8][4] = {
  {1,0,0,0},{1,1,0,0},{0,1,0,0},{0,1,1,0},
  {0,0,1,0},{0,0,1,1},{0,0,0,1},{1,0,0,1}
};

// ---------------- SETUP ----------------
void setup() {
  Serial.begin(115200);

  for (int i = 0; i < 4; i++) {
    pinMode(BASE_PINS[i], OUTPUT);
    pinMode(JOINT_PINS[i], OUTPUT);
    pinMode(EXT_PINS[i], OUTPUT);
  }

  disableCoils(BASE_PINS);
  disableCoils(JOINT_PINS);
  disableCoils(EXT_PINS);

  clampServo.attach(SERVO_PIN);
  clampServo.write(10);
}

// ---------------- MAIN LOOP ----------------
void loop() {
  handleSerial();
  updateStepper(base);
  updateStepper(joint);
  updateStepper(ext);
}

// ---------------- SERIAL HANDLER ----------------
void handleSerial() {
  if (Serial.available()) {
    String jsonStr = Serial.readStringUntil('\n');

    StaticJsonDocument<256> doc;
    if (deserializeJson(doc, jsonStr)) {
      Serial.println(F("{\"status\":\"error\",\"msg\":\"bad json\"}"));
      return;
    }

    const char* cmd = doc["cmd"];

    if (strcmp(cmd, "arm") == 0) {
      const char* motor = doc["motor"];
      int steps = doc["steps"];
      int dir   = doc["dir"];
      int speed = doc["speed"] | 3;

      if (steps <= 0 || (dir != 0 && dir != 1)) {
        Serial.println(F("{\"status\":\"error\",\"msg\":\"invalid params\"}"));
        return;
      }

      StepperState* target = NULL;

      if (strcmp(motor, "base") == 0) target = &base;
      else if (strcmp(motor, "joint") == 0) target = &joint;
      else if (strcmp(motor, "ext") == 0) target = &ext;

      if (target == NULL) {
        Serial.println(F("{\"status\":\"error\",\"msg\":\"unknown motor\"}"));
        return;
      }

      target->stepsRemaining = steps;
      target->dir = dir;
      target->stepDelay = constrain(speed, 1, 10);

      Serial.println(F("{\"status\":\"ok\"}"));
    }

    else if (strcmp(cmd, "clamp") == 0) {
      int angle = constrain(doc["angle"], 10, 120);
      clampServo.write(angle);
      Serial.println(F("{\"status\":\"ok\"}"));
    }
  }
}

// ---------------- STEPPER UPDATE ----------------
void updateStepper(StepperState &s) {
  if (s.stepsRemaining <= 0) return;

  unsigned long now = millis();

  if (now - s.lastStepTime >= s.stepDelay) {
    s.lastStepTime = now;

    for (int i = 0; i < 4; i++) {
      digitalWrite(s.pins[i], stepsMatrix[s.stepIndex][i]);
    }

    if (s.dir == 1)
      s.stepIndex = (s.stepIndex + 1) % 8;
    else
      s.stepIndex = (s.stepIndex - 1 + 8) % 8;

    s.stepsRemaining--;

    if (s.stepsRemaining == 0) {
      disableCoils(s.pins);
    }
  }
}

// ---------------- DISABLE COILS ----------------
void disableCoils(const int* pins) {
  for (int i = 0; i < 4; i++) {
    digitalWrite(pins[i], LOW);
  }
}