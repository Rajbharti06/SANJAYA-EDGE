"""
Download the Kaggle Real-Time Traffic Video Dataset (500 videos).
Run once before starting the backend:
    python download_kaggle.py

Requires:
    pip install kagglehub
    Kaggle API credentials set up (~/.kaggle/kaggle.json or KAGGLE_USERNAME/KAGGLE_KEY env vars)
"""
import os
import shutil
import kagglehub

VIDEOS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "Videos"))
DATASET    = "unidpro/real-time-traffic-video-dataset"

VIDEO_EXTENSIONS = {".mp4", ".webm", ".avi", ".mov", ".mkv"}


def main():
    print(f"Downloading dataset: {DATASET}")
    dataset_path = kagglehub.dataset_download(DATASET)
    print(f"Dataset downloaded to: {dataset_path}")

    os.makedirs(VIDEOS_DIR, exist_ok=True)

    copied = 0
    for root, dirs, files in os.walk(dataset_path):
        for fname in sorted(files):
            if os.path.splitext(fname)[1].lower() in VIDEO_EXTENSIONS:
                src = os.path.join(root, fname)
                dst = os.path.join(VIDEOS_DIR, fname)
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                    print(f"  Copied: {fname}")
                    copied += 1
                else:
                    print(f"  Skipped (exists): {fname}")

    print(f"\nDone. {copied} new video(s) copied to: {VIDEOS_DIR}")


if __name__ == "__main__":
    main()
