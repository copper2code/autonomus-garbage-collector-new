import cv2
import os

# Put your two video paths here
bin_video_path = "/mnt/repos/code/autonomus-garbage-collector/video/bin.mp4"
bg_video_path = "/mnt/repos/code/autonomus-garbage-collector/video/bg.mp4"
dataset_dir = "bin_images_training"

def extract_frames(video_path, output_dir, frame_skip=5):
    if not os.path.exists(video_path):
        print(f"⚠ Skipping: Video '{video_path}' not found!")
        return

    os.makedirs(output_dir, exist_ok=True)
    
    existing_files = os.listdir(output_dir)
    start_idx = len(existing_files)
    
    cap = cv2.VideoCapture(video_path)
    count = 0
    saved = 0
    
    print(f"Extracting frames from {video_path} -> {output_dir}...")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        if count % frame_skip == 0:
            frame = cv2.resize(frame, (160, 120))
            filename = os.path.join(output_dir, f"img_{start_idx + saved:05d}.jpg")
            cv2.imwrite(filename, frame)
            saved += 1
            
        count += 1

    cap.release()
    print(f"✓ Saved {saved} images!")

if __name__ == "__main__":
    print("====================================")
    print("  DUAL-DATASET GENERATOR SCRIPT")
    print("====================================")
    
    # 1. Process the Bin video into the garbage_bin folder
    extract_frames(bin_video_path, os.path.join(dataset_dir, "garbage_bin"), frame_skip=5)
    
    # 2. Process the Background video into the background folder
    extract_frames(bg_video_path, os.path.join(dataset_dir, "background"), frame_skip=5)
    
    print(f"\n✅ All done! You can now run train_bin_on_pc.py!")
