import os
import threading
import logging
import time
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
import PIL.Image

import config

logger = logging.getLogger(__name__)

# Reusable lightweight CNN architecture
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
        # Using adaptive pool to force a fixed flattened size regardless of input resolution
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

class DrivingDataset(Dataset):
    def __init__(self, data_dir, transform=None):
        self.data_dir = data_dir
        self.transform = transform
        self.samples = []
        
        # Load driving data. Assume directory structure:
        # data/driving/left/123.jpg, data/driving/forward/124.jpg, etc.
        class_to_idx = {cls: i for i, cls in enumerate(config.DRIVING_CLASSES)}
        
        for cls in config.DRIVING_CLASSES:
            cls_dir = os.path.join(self.data_dir, cls)
            if not os.path.exists(cls_dir): continue
            
            for f in os.listdir(cls_dir):
                if f.endswith(('.jpg', '.png', '.jpeg')):
                    self.samples.append((os.path.join(cls_dir, f), class_to_idx[cls]))
                    
    def __len__(self):
        return len(self.samples)
        
    def __getitem__(self, idx):
        img_path, label = self.samples[idx]
        image = PIL.Image.open(img_path).convert('RGB')
        if self.transform:
            image = self.transform(image)
        return image, label

def train_driving_model_in_background(shared_state):
    """
    Trains the collected driving data asynchronously and updates the shared state.
    """
    def worker():
        shared_state.training_status = "training"
        shared_state.training_progress = 0
        logger.info("Starting background training of Driving Model...")
        
        device = torch.device('cpu') # Prefer CPU on Pi to prevent memory issues for lightweight tasks
        epochs = 10
        batch_size = 16
        lr = 0.001
        
        transform = transforms.Compose([
            transforms.Resize((config.MODEL_INPUT_HEIGHT, config.MODEL_INPUT_WIDTH)),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        
        dataset = DrivingDataset(config.DRIVING_DATA_DIR, transform=transform)
        if len(dataset) < 10:
            logger.error(f"Not enough data to train. Found {len(dataset)} samples.")
            shared_state.training_status = "error_no_data"
            return
            
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        model = CompactCNN(num_classes=len(config.DRIVING_CLASSES)).to(device)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=lr)
        
        if not os.path.exists(config.MODELS_DIR):
            os.makedirs(config.MODELS_DIR)
            
        for epoch in range(epochs):
            model.train()
            running_loss = 0.0
            
            for inputs, labels in loader:
                inputs, labels = inputs.to(device), labels.to(device)
                optimizer.zero_grad()
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                running_loss += loss.item()
                
            shared_state.training_progress = int(((epoch + 1) / epochs) * 100)
            logger.info(f"Training Driving Epoch {epoch+1}/{epochs} - Loss: {running_loss/len(loader):.4f}")
            
        torch.save(model.state_dict(), config.DRIVING_MODEL)
        logger.info(f"Driving model successfully saved to {config.DRIVING_MODEL}")
        
        shared_state.training_status = "done"
        
        # Reload model directly in the vision parser without restart
        shared_state.dual_inference.reload_driving_model()
        
    t = threading.Thread(target=worker, daemon=True)
    t.start()
