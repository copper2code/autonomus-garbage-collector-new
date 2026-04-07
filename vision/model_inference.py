import os
import cv2
import torch
import PIL.Image
from torchvision import transforms
import logging

import config
from ml.training_pipeline import CompactCNN

logger = logging.getLogger(__name__)

# Optimize PyTorch for Pi 4B quad-core ARM Cortex-A72
torch.set_num_threads(4)


class DualModelInference:
    """Manages inference for both the Autonomous Driving CNN and Garbage Bin CNN."""
    def __init__(self):
        self.device = torch.device('cpu')
        
        # Init Driving Model
        self.driving_model = CompactCNN(num_classes=len(config.DRIVING_CLASSES)).to(self.device)
        self.driving_model.eval()
        self.driving_loaded = False
        
        # Init Bin Model
        self.bin_model = CompactCNN(num_classes=len(config.BIN_CLASSES)).to(self.device)
        self.bin_model.eval()
        self.bin_loaded = False

        self.transform = transforms.Compose([
            transforms.Resize((config.MODEL_INPUT_HEIGHT, config.MODEL_INPUT_WIDTH)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        self.reload_driving_model()
        self.reload_bin_model()

    def reload_driving_model(self):
        if os.path.exists(config.DRIVING_MODEL):
            try:
                self.driving_model.load_state_dict(
                    torch.load(config.DRIVING_MODEL, map_location=self.device, weights_only=True)
                )
                self.driving_model.eval()
                self.driving_loaded = True
                logger.info(f"✓ Loaded Driving Model from {config.DRIVING_MODEL}")
            except Exception as e:
                logger.error(f"Failed loading Driving Model: {e}")
                self.driving_loaded = False
        else:
            logger.warning("No Driving Model found. Train the model first via Training Mode!")
            self.driving_loaded = False

    def reload_bin_model(self):
        if os.path.exists(config.GARBAGE_BIN_MODEL):
            try:
                self.bin_model.load_state_dict(
                    torch.load(config.GARBAGE_BIN_MODEL, map_location=self.device, weights_only=True)
                )
                self.bin_model.eval()
                self.bin_loaded = True
                logger.info(f"✓ Loaded Bin Model from {config.GARBAGE_BIN_MODEL}")
            except Exception as e:
                logger.error(f"Failed loading Bin Model: {e}")
                self.bin_loaded = False
        else:
            self.bin_loaded = False
            logger.info("No Bin Detection Model found — bin detection disabled.")

    def predict(self, frame):
        """
        Runs both CNNs on the single frame.
        Returns: (driving_command, bin_detected, bin_confidence)
        """
        driving_cmd = "stop"
        bin_detected = False
        bin_conf = 0.0

        if frame is None:
            return driving_cmd, bin_detected, bin_conf

        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = PIL.Image.fromarray(rgb)
            img_tensor = self.transform(pil_img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                # Dual Run: Bin Detection
                if self.bin_loaded:
                    bin_out = self.bin_model(img_tensor)
                    bin_probs = torch.nn.functional.softmax(bin_out[0], dim=0)
                    max_bin_prob, bin_idx = torch.max(bin_probs, 0)
                    
                    if bin_idx.item() != 0 and max_bin_prob.item() > config.BIN_DETECT_THRESHOLD:
                        bin_detected = True
                        bin_conf = max_bin_prob.item()

                # Dual Run: Driving prediction
                if self.driving_loaded and not bin_detected:
                    drv_out = self.driving_model(img_tensor)
                    drv_probs = torch.nn.functional.softmax(drv_out[0], dim=0)
                    _, drv_idx = torch.max(drv_probs, 0)
                    driving_cmd = config.DRIVING_CLASSES[drv_idx.item()]

        except Exception as e:
            logger.error(f"Inference error: {e}")

        return driving_cmd, bin_detected, bin_conf
