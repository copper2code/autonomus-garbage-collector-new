import cv2
import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image

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
    model_path = "garbage_bin.pth"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # The folders you created dictate the class IDs automatically in PyTorch.
    # Alphabetical order: 'background' is 0, 'garbage_bin' is 1
    classes = ["Background", "Garbage Bin"]
    
    model = CompactCNN(num_classes=2).to(device)
    
    # Load your freshly trained model!
    try:
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()
        print(f"✅ Loaded {model_path} successfully on {device}!")
    except Exception as e:
        print(f"❌ Error: Could not find or load '{model_path}'.")
        print("Make sure you run 'train_bin_on_pc.py' first!")
        return

    # Must match the exact transforms from training
    transform = transforms.Compose([
        transforms.Resize((120, 160)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # Open your laptop webcam (0) OR replace with your video path string
    # e.g., cap = cv2.VideoCapture("video/VID20260411193842.mp4")
    cap = cv2.VideoCapture(0)
    
    print("Starting video feed... Press 'q' to quit.")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # --- 1. OPEN-CV RED SQUARE DETECTION ---
        # Since you painted it bright red, we can mathematically draw a box around it!
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Red wraps around the color wheel in HSV, so we need two masks
        lower_red_1 = torch.tensor([0, 100, 100]) # Not actual torch, just using normal python tuples
        mask1 = cv2.inRange(hsv, (0, 100, 50), (10, 255, 255))
        mask2 = cv2.inRange(hsv, (160, 100, 50), (180, 255, 255))
        red_mask = mask1 + mask2
        
        # Find the contours of the red blob
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bin_box = None
        if contours:
            # Get the largest red blob
            largest_contour = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest_contour) > 500: # Filter out tiny red specks
                x, y, w, h = cv2.boundingRect(largest_contour)
                bin_box = (x, y, w, h)
                # Draw the square!
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 4)
                cv2.putText(frame, "TARGET LOCK", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # --- 2. NEURAL NETWORK VALIDATION ---
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        input_tensor = transform(pil_img).unsqueeze(0).to(device)
        
        with torch.no_grad():
            outputs = model(input_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            confidence, predicted_class_idx = torch.max(probabilities, 1)
            
        pred_idx = predicted_class_idx.item()
        conf_val = confidence.item()
        label = classes[pred_idx]
        
        # FIX: The AI sometimes hallucinates when the background changes. 
        # Since we know the bin is red, we force the AI to only say "Bin Detected" 
        # if the red square actually exists in the frame!
        if label == "Garbage Bin" and bin_box is not None:
            color = (0, 255, 0)
            text = f"BINGO! Dustbin Detected ({conf_val*100:.1f}%)"
        else:
            color = (0, 0, 255)
            text = f"Searching... (AI Conf: {conf_val*100:.1f}%)"
            
        cv2.putText(frame, text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
        cv2.imshow("Dustbin AI Testing", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
