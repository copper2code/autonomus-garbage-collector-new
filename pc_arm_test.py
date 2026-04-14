import cv2
import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image
import time
import os

from communication.arduino_serial import SerialManager
from control.arm_control import ArmController
import config

# 1. MATCH THE MODEL ARCHITECTURE
class CompactCNN(nn.Module):
    def __init__(self, num_classes):
        super(CompactCNN, self).__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Conv2d(16, 32, kernel_size=3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )
        self.adaptive_pool = nn.AdaptiveAvgPool2d((7, 7))
        self.classifier = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(32 * 7 * 7, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, num_classes)
        )

    def forward(self, x):
        x = self.features(x)
        x = self.adaptive_pool(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x

def main():
    print("Initializing Arm Controller (PC Version)...")
    try:
        # Initialize serial and arm
        serial_man = SerialManager()
        arm = ArmController(serial_man)
        # Attempt to set clamp open if arm is connected
        if serial_man.arm.connected:
            arm.set_clamp(config.CLAMP_OPEN_ANGLE)
            print("✅ Connected to Arm Arduino!")
        else:
            print("⚠ Warning: Arm Arduino not detected. Inference will run but arm won't move.")
    except Exception as e:
        print(f"❌ Error initializing serial/arm: {e}")
        return

    model_path = "garbage_bin.pth"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    classes = ["Background", "Garbage Bin"]
    
    model = CompactCNN(num_classes=2).to(device)
    
    try:
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()
        print(f"✅ Loaded {model_path} successfully on {device}!")
    except Exception as e:
        print(f"❌ Error: Could not find or load '{model_path}'.")
        print("Make sure you run 'train_bin_on_pc.py' first!")
        return

    transform = transforms.Compose([
        transforms.Resize((120, 160)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    cap = cv2.VideoCapture(0)
    
    print("Starting video feed... Press 'q' to quit.")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Red masks
        mask1 = cv2.inRange(hsv, (0, 100, 50), (10, 255, 255))
        mask2 = cv2.inRange(hsv, (160, 100, 50), (180, 255, 255))
        red_mask = mask1 + mask2
        
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bin_box = None
        
        # Draw central screen crosshair (HUD)
        height, width, _ = frame.shape
        screen_cx, screen_cy = width // 2, height // 2
        cv2.line(frame, (screen_cx - 20, screen_cy), (screen_cx + 20, screen_cy), (255, 255, 255), 2)
        cv2.line(frame, (screen_cx, screen_cy - 20), (screen_cx, screen_cy + 20), (255, 255, 255), 2)
        
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest_contour) > 500:
                x, y, w, h = cv2.boundingRect(largest_contour)
                bin_box = (x, y, w, h)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 4)
                
                # Draw center target dot
                target_cx, target_cy = x + w // 2, y + h // 2
                cv2.circle(frame, (target_cx, target_cy), 5, (0, 0, 255), -1)
                
                # Draw tracking line from center of screen to bin center
                cv2.line(frame, (screen_cx, screen_cy), (target_cx, target_cy), (0, 255, 255), 2)
                
                cv2.putText(frame, "TARGET LOCK", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        input_tensor = transform(pil_img).unsqueeze(0).to(device)
        
        with torch.no_grad():
            outputs = model(input_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            confidence, predicted_class_idx = torch.max(probabilities, 1)
            
        pred_idx = predicted_class_idx.item()
        conf_val = confidence.item()
        label = classes[pred_idx]
        
        if label == "Garbage Bin" and bin_box is not None:
            color = (0, 255, 0)
            text = f"BINGO! Dustbin Detected ({conf_val*100:.1f}%)"
            
            # TRIGGER ARM SEQUENCE IF NOT ALREADY RUNNING
            if not arm.sequence_running:
                print(f"🔥 Target locked! Confidence: {conf_val*100:.1f}% -> Triggering Arm Collection!")
                arm.trigger_collection_sequence()
            else:
                cv2.putText(frame, "ARM BUSY...", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        else:
            color = (0, 0, 255)
            text = f"Searching... (AI Conf: {conf_val*100:.1f}%)"
            
        cv2.putText(frame, text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
        cv2.imshow("PC Arm Test - Dustbin AI", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    if serial_man:
        serial_man.close_all()

if __name__ == "__main__":
    main()
