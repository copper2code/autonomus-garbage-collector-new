#include <ArduinoJson.h>

// L298N Motor Driver Pins
const int EN_A = 9;   // Left motor speed
const int IN1 = 8;    // Left motor dir 1
const int IN2 = 7;    // Left motor dir 2
const int IN3 = 5;    // Right motor dir 1
const int IN4 = 4;    // Right motor dir 2
const int EN_B = 3;   // Right motor speed

unsigned long lastCmdTime = 0;
const int WATCHDOG_TIMEOUT = 1000; // ms

void setup() {
  Serial.begin(115200);
  
  pinMode(EN_A, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  pinMode(EN_B, OUTPUT);
  
  stopCar();
}

void loop() {
  if (Serial.available() > 0) {
    String jsonStr = Serial.readStringUntil('\n');
    
    StaticJsonDocument<200> doc;
    DeserializationError error = deserializeJson(doc, jsonStr);
    
    if (error) {
      Serial.println(F("{\"status\": \"error\", \"msg\": \"invalid json\"}"));
      return;
    }
    
    const char* cmd = doc["cmd"];
    if (strcmp(cmd, "move") == 0) {
      const char* dir = doc["dir"];
      int speed = doc["speed"];
      
      moveCar(dir, speed);
      lastCmdTime = millis();
      Serial.println(F("{\"status\": \"ok\"}"));
    }
  }
  
  // Watchdog: Stop the car if no command received within timeout
  if (millis() - lastCmdTime > WATCHDOG_TIMEOUT) {
    stopCar();
  }
}

void setMotors(int leftSpeed, bool l_fwd, int rightSpeed, bool r_fwd) {
  analogWrite(EN_A, leftSpeed);
  analogWrite(EN_B, rightSpeed);
  
  digitalWrite(IN1, l_fwd ? HIGH : LOW);
  digitalWrite(IN2, l_fwd ? LOW : HIGH);
  
  digitalWrite(IN3, r_fwd ? HIGH : LOW);
  digitalWrite(IN4, r_fwd ? LOW : HIGH);
}

void stopCar() {
  setMotors(0, true, 0, true);
}

void moveCar(const char* dir, int speed) {
  if (strcmp(dir, "forward") == 0) {
    setMotors(speed, true, speed, true);
  } else if (strcmp(dir, "backward") == 0) {
    setMotors(speed, false, speed, false);
  } else if (strcmp(dir, "left") == 0) {
    setMotors(speed, false, speed, true);
  } else if (strcmp(dir, "right") == 0) {
    setMotors(speed, true, speed, false);
  } else if (strcmp(dir, "stop") == 0) {
    stopCar();
  }
}
