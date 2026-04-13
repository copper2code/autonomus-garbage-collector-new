import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

# ══════════════════════════════════════════════════════════════════
# BIN DETECTION TRAINER (Run this on your PC / Laptop / Colab)
# ══════════════════════════════════════════════════════════════════

# 1. SETTINGS
DATASET_DIR = "bin_images_training"  # Put your images here
NUM_EPOCHS = 35
BATCH_SIZE = 16
LEARNING_RATE = 0.0001
IMAGE_WIDTH = 160
IMAGE_HEIGHT = 120

# 2. MATCH THE ROBOT'S EXACT NEURAL NETWORK ARCHITECTURE
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

# 3. TRAINING LOOP
def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on: {device}")

    # Ensure dataset is structured correctly
    if not os.path.exists(DATASET_DIR):
        print(f"ERROR: Dataset directory '{DATASET_DIR}' not found!")
        print("Please create it and add two subfolders:")
        print(f"   {DATASET_DIR}/background/")
        print(f"   {DATASET_DIR}/garbage_bin/")
        return

    # Image processing pipeline (matching the Pi's preprocessing)
    transform = transforms.Compose([
        transforms.Resize((IMAGE_HEIGHT, IMAGE_WIDTH)),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # Load dataset
    dataset = datasets.ImageFolder(root=DATASET_DIR, transform=transform)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    
    print(f"Found {len(dataset)} images belonging to {len(dataset.classes)} classes: {dataset.classes}")
    
    if len(dataset.classes) != 2:
        print("WARNING: The robot expects exactly 2 classes: 'background' and 'garbage_bin'")

    # Initialize model
    model = CompactCNN(num_classes=len(dataset.classes)).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

    # Train
    for epoch in range(NUM_EPOCHS):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        
        for inputs, labels in dataloader:
            inputs, labels = inputs.to(device), labels.to(device)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            
        print(f"Epoch [{epoch+1}/{NUM_EPOCHS}] - Loss: {running_loss/len(dataloader):.4f} - Accuracy: {100 * correct / total:.2f}%")

    # Save the model
    save_path = "garbage_bin.pth"
    torch.save(model.state_dict(), save_path)
    print(f"\\n✅ Training Complete! Model saved as '{save_path}'")
    print("Next step: Transfer 'garbage_bin.pth' to the Raspberry Pi inside the 'models/' directory.")

if __name__ == "__main__":
    main()
