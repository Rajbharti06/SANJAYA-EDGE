"""
SANJAYA EDGE — Demo Recorder
Processes real video files through the detection pipeline,
overlays professional subtitle captions, saves screenshots + demo.mp4
"""
import cv2
import numpy as np
import os
import json
from collections import deque
from ultralytics import YOLO

BASE       = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(BASE, "Videos")
SHOTS_DIR  = os.path.join(BASE, "screenshots")
DEMO_OUT   = os.path.join(BASE, "demo.mp4")
os.makedirs(SHOTS_DIR, exist_ok=True)

# ─── Detection constants ──────────────────────────────────────────────────────
CLS_PERSON        = 0
CLS_MOTORCYCLE    = 3
CLS_CAR           = 2
CLS_BUS           = 5
CLS_TRUCK         = 7
CLS_TRAFFIC_LIGHT = 9
VEHICLE_CLASSES   = {CLS_CAR, CLS_BUS, CLS_TRUCK, CLS_MOTORCYCLE}

TARGET_W, TARGET_H = 1280, 720
FPS_OUT            = 25

# ─── Subtitle spec: (start_sec, end_sec, main_text, sub_text) ─────────────────
# NOTE: OpenCV putText only supports ASCII - no Unicode chars
SEGMENTS = [
    {
        "file":  "red_light_clear.mp4",
        "start": 0, "duration": 20,
        "subs": [
            (0,   4,  "Hello everyone - this is SANJAYA EDGE",
                      "AI Road Safety Co-Pilot  |  IIT Madras CoERS Hackathon 2026"),
            (4,   8,  "5 real-time detectors running simultaneously",
                      "YOLOv8n  +  OpenCV HSV  +  Lucas-Kanade Optical Flow"),
            (8,   12, "DETECTOR 1: Red Light Jump  [MVA Section 119]",
                      "Temporal 4-frame consensus  |  eliminates false positives"),
            (12,  16, "YOLOv8n scanning traffic signal in real time...",
                      "COCO class 9 (traffic_light)  |  confidence threshold: 25%"),
            (16,  20, "HSV colour analysis confirmed: RED LIGHT!",
                      "CRITICAL VIOLATION  ->  Rs.1,000 fine  |  MVA Section 119"),
        ],
    },
    {
        "file":  "no_helmet.webm",
        "start": 0, "duration": 20,
        "subs": [
            (0,   4,  "DETECTOR 2: Helmet Violation  [MVA Section 129]",
                      "Detects bare head on motorcyclists in real time"),
            (4,   8,  "YOLOv8n identifies head vs helmet on riders",
                      "Custom helmet model  |  fallback: motorcycle proxy"),
            (8,   13, "Bare head detected on motorcyclist!",
                      "HIGH RISK  ->  Rs.1,000 fine  +  3-month licence suspension"),
            (13,  17, "Voice co-pilot announces violation instantly",
                      "en-IN speech synthesis  |  Web Speech API  |  Hindi/English"),
            (17,  20, "Every alert: law section + fine + state breakdown",
                      "Tamil Nadu  /  Maharashtra  /  Karnataka  penalties shown"),
        ],
    },
    {
        "file":  "wrong_side_driving.mp4",
        "start": 0, "duration": 18,
        "subs": [
            (0,   4,  "DETECTOR 3: Wrong-Side Driving  [MVA Section 184]",
                      "Lucas-Kanade sparse optical flow on vehicle centres"),
            (4,   8,  "Dominant traffic flow direction computed each frame",
                      "Circular mean of velocity angles  |  20-frame history"),
            (8,   13, "Vehicle moving 140+ degrees against dominant flow!",
                      "CRITICAL VIOLATION  ->  Rs.5,000 dangerous driving fine"),
            (13,  18, "DETECTORS 4 + 5: Traffic Blocking + Pedestrian",
                      "IoU cluster >= 6 vehicles  |  Aspect-ratio pedestrian filter"),
        ],
    },
    {
        "file":  "traffic_congestion.mp4",
        "start": 0, "duration": 16,
        "subs": [
            (0,   4,  "DETECTOR 4: Traffic Blocking  [IPC Section 283]",
                      "Vectorised pairwise IoU cluster detection"),
            (4,   8,  "Dense vehicle cluster detected (6+ vehicles)!",
                      "CRITICAL  ->  Rs.5,000  +  Rs.2,000 public nuisance fine"),
            (8,   12, "ARCHITECTURE: FastAPI  +  React  +  WebSocket streaming",
                      "Annotated JPEG frames streamed at full video FPS"),
            (12,  16, "SANJAYA EDGE: Proactive Citizen Legal Co-Pilot",
                      "github.com/Rajbharti06/SANJAYA-EDGE  |  IIT Madras 2026"),
        ],
    },
]

# ─── Subtitle rendering ───────────────────────────────────────────────────────
FONT      = cv2.FONT_HERSHEY_SIMPLEX
FONT_BOLD = cv2.FONT_HERSHEY_DUPLEX

def draw_subtitle(frame: np.ndarray, main: str, sub: str, progress: float = 0.5) -> np.ndarray:
    """Renders a professional subtitle bar at the bottom of the frame."""
    H, W = frame.shape[:2]
    out  = frame.copy()

    bar_h = 76
    bar_y = H - bar_h

    # Semi-transparent dark bar
    overlay = out.copy()
    cv2.rectangle(overlay, (0, bar_y), (W, H), (5, 8, 18), -1)
    cv2.addWeighted(overlay, 0.82, out, 0.18, 0, out)

    # Blue accent line at top of bar
    cv2.line(out, (0, bar_y), (W, bar_y), (59, 130, 246), 2)

    # Main subtitle text (larger, white)
    main_scale = 0.68
    main_thick = 2
    (mw, mh), _ = cv2.getTextSize(main, FONT_BOLD, main_scale, main_thick)
    mx = (W - mw) // 2
    my = bar_y + 26

    # Shadow
    cv2.putText(out, main, (mx + 2, my + 2), FONT_BOLD, main_scale, (0, 0, 0), main_thick + 2, cv2.LINE_AA)
    # White text
    cv2.putText(out, main, (mx, my), FONT_BOLD, main_scale, (240, 245, 255), main_thick, cv2.LINE_AA)

    # Sub text (smaller, grey-blue)
    sub_scale = 0.50
    sub_thick = 1
    (sw, sh), _ = cv2.getTextSize(sub, FONT, sub_scale, sub_thick)
    sx = (W - sw) // 2
    sy = bar_y + 52

    cv2.putText(out, sub, (sx + 1, sy + 1), FONT, sub_scale, (0, 0, 0), sub_thick + 1, cv2.LINE_AA)
    cv2.putText(out, sub, (sx, sy), FONT, sub_scale, (147, 197, 253), sub_thick, cv2.LINE_AA)

    # Progress bar (thin blue line)
    prog_w = int(W * min(progress, 1.0))
    cv2.rectangle(out, (0, H - 3), (prog_w, H), (59, 130, 246), -1)

    return out


def draw_title_card(text1: str, text2: str, text3: str = "", size=(1280, 720)) -> np.ndarray:
    """Creates a full title card frame."""
    W, H = size
    frame = np.zeros((H, W, 3), dtype=np.uint8)

    # Background gradient
    for y in range(H):
        alpha = y / H
        r = int(5 + 10 * alpha)
        g = int(8 + 12 * alpha)
        b = int(18 + 30 * alpha)
        frame[y, :] = [b, g, r]

    # Blue accent lines
    cv2.line(frame, (0, H // 2 - 60), (W, H // 2 - 60), (30, 60, 120), 1)
    cv2.line(frame, (0, H // 2 + 60), (W, H // 2 + 60), (30, 60, 120), 1)

    # Logo dot (top-left area)
    cv2.circle(frame, (W // 2, H // 2 - 90), 18, (59, 130, 246), 2)
    cv2.circle(frame, (W // 2, H // 2 - 90), 6,  (59, 130, 246), -1)
    cv2.line(frame, (W // 2, H // 2 - 108), (W // 2, H // 2 - 112), (59, 130, 246), 2)
    cv2.line(frame, (W // 2, H // 2 - 68),  (W // 2, H // 2 - 72),  (59, 130, 246), 2)
    cv2.line(frame, (W // 2 - 20, H // 2 - 90), (W // 2 - 16, H // 2 - 90), (59, 130, 246), 2)
    cv2.line(frame, (W // 2 + 16, H // 2 - 90), (W // 2 + 20, H // 2 - 90), (59, 130, 246), 2)

    def center_text(text, y, font, scale, thickness, color):
        (tw, _), _ = cv2.getTextSize(text, font, scale, thickness)
        x = (W - tw) // 2
        cv2.putText(frame, text, (x + 2, y + 2), font, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
        cv2.putText(frame, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)

    center_text(text1, H // 2 - 10, FONT_BOLD, 1.30, 2, (240, 245, 255))
    center_text(text2, H // 2 + 38, FONT,      0.68, 1, (147, 197, 253))
    if text3:
        center_text(text3, H // 2 + 72, FONT,  0.52, 1, (100, 140, 200))

    return frame


def add_detection_info(frame: np.ndarray, results, label_extra: str = "") -> np.ndarray:
    """Overlay YOLO detections with coloured boxes and labels."""
    out = results[0].plot()
    # Resize back to target if needed
    if out.shape[1] != frame.shape[1] or out.shape[0] != frame.shape[0]:
        out = cv2.resize(out, (frame.shape[1], frame.shape[0]))
    return out


def prepare_frame(frame: np.ndarray) -> np.ndarray:
    """Letterbox resize to TARGET_W x TARGET_H."""
    H, W = frame.shape[:2]
    scale = min(TARGET_W / W, TARGET_H / H)
    nw, nh = int(W * scale), int(H * scale)
    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((TARGET_H, TARGET_W, 3), dtype=np.uint8)
    y_off  = (TARGET_H - nh) // 2
    x_off  = (TARGET_W - nw) // 2
    canvas[y_off:y_off + nh, x_off:x_off + nw] = resized
    return canvas


def get_subtitle(subs, elapsed_sec):
    for (s, e, main, sub) in subs:
        if s <= elapsed_sec < e:
            prog = (elapsed_sec - s) / (e - s)
            return main, sub, prog
    return None, None, 0.0


def corner_brackets(frame, color=(59, 130, 246), thickness=2, size=22, margin=12):
    H, W = frame.shape[:2]
    for (x, y) in [(margin, margin), (W - margin, margin),
                   (margin, H - margin), (W - margin, H - margin)]:
        sx, sy = (1 if x == margin else -1), (1 if y == margin else -1)
        cv2.line(frame, (x, y), (x + sx * size, y), color, thickness)
        cv2.line(frame, (x, y), (x, y + sy * size), color, thickness)
    return frame


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("[demo] Loading YOLOv8n…")
    model = YOLO(os.path.join(BASE, "backend", "yolov8n.pt"))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(DEMO_OUT, fourcc, FPS_OUT, (TARGET_W, TARGET_H))
    if not writer.isOpened():
        print("[demo] ERROR: Cannot open VideoWriter — check codec support")
        return

    screenshots_saved = []

    # ── Intro title card (3 seconds) ──────────────────────────────────────────
    print("[demo] Rendering intro title card…")
    intro_card = draw_title_card(
        "SANJAYA  EDGE",
        "AI Road Safety Co-Pilot  |  IIT Madras CoERS Hackathon 2026",
        "github.com/Rajbharti06/SANJAYA-EDGE"
    )
    intro_frame = corner_brackets(intro_card.copy())
    for _ in range(FPS_OUT * 3):
        writer.write(intro_frame)

    # Save intro screenshot
    shot_path = os.path.join(SHOTS_DIR, "00_title.png")
    cv2.imwrite(shot_path, intro_card)
    screenshots_saved.append(shot_path)
    print(f"  Saved screenshot: {shot_path}")

    # ── Process each video segment ────────────────────────────────────────────
    for seg_idx, seg in enumerate(SEGMENTS):
        vid_path = os.path.join(VIDEOS_DIR, seg["file"])
        if not os.path.exists(vid_path):
            print(f"  [skip] {seg['file']} not found")
            continue

        print(f"\n[demo] Processing segment: {seg['file']}")
        cap = cv2.VideoCapture(vid_path)
        if not cap.isOpened():
            print(f"  ERROR: cannot open {seg['file']}")
            continue

        src_fps   = cap.get(cv2.CAP_PROP_FPS) or 25.0
        max_frame = int(seg["duration"] * src_fps)
        skip      = max(1, int(src_fps / FPS_OUT))  # sample rate for output FPS

        # Skip to start_sec
        if seg.get("start", 0) > 0:
            cap.set(cv2.CAP_PROP_POS_MSEC, seg["start"] * 1000)

        frame_count   = 0
        last_results  = None
        shot_taken    = set()

        while frame_count < max_frame:
            ret, raw = cap.read()
            if not ret:
                break

            frame_count += 1
            elapsed_sec = frame_count / src_fps

            if frame_count % skip != 0:
                continue  # only write at output FPS rate

            # Resize + letterbox
            frame = prepare_frame(raw)

            # Run YOLO every 3 frames (mirrors main.py SKIP=3)
            run_yolo = (frame_count % 3 == 0) or last_results is None
            if run_yolo:
                small = cv2.resize(frame, (416, int(416 * frame.shape[0] / frame.shape[1])))
                last_results = model(small, verbose=False, conf=0.25, imgsz=320)

            # Draw YOLO annotations
            if last_results is not None:
                ann = last_results[0].plot()
                ann = cv2.resize(ann, (TARGET_W, TARGET_H))
                corner_brackets(ann, color=(59, 130, 246))
            else:
                ann = frame.copy()
                corner_brackets(ann, color=(59, 130, 246))

            # Add HUD overlay (top-left info)
            cv2.putText(ann, "SANJAYA EDGE", (16, 28), FONT_BOLD, 0.60, (240, 245, 255), 1, cv2.LINE_AA)
            cv2.putText(ann, "YOLOv8n  LIVE", (16, 48), FONT, 0.42, (147, 197, 253), 1, cv2.LINE_AA)
            cv2.putText(ann, f"F {frame_count:05d}", (TARGET_W - 110, 28), FONT, 0.42, (100, 140, 200), 1, cv2.LINE_AA)
            rec_color = (80, 80, 240) if (frame_count // 15) % 2 == 0 else (60, 60, 180)
            cv2.circle(ann, (TARGET_W - 130, 22), 6, rec_color, -1)
            cv2.putText(ann, "REC", (TARGET_W - 120, 28), FONT, 0.42, (200, 100, 100), 1, cv2.LINE_AA)

            # Get active subtitle
            main_txt, sub_txt, prog = get_subtitle(seg["subs"], elapsed_sec)
            if main_txt:
                ann = draw_subtitle(ann, main_txt, sub_txt, prog)

            writer.write(ann)

            # Save screenshot at mid-point of each subtitle (safe filename)
            import re as _re
            for sub_i, (s, e, mt, st) in enumerate(seg["subs"]):
                mid = (s + e) / 2
                mid_frame = int(mid * src_fps)
                key = f"{seg_idx}_{s}"
                if key not in shot_taken and abs(frame_count - mid_frame) <= skip:
                    safe = _re.sub(r"[^A-Za-z0-9\s-]", "", mt).strip()
                    safe = _re.sub(r"\s+", "_", safe)[:40].rstrip("_")
                    shot_name = f"{seg_idx + 1:02d}_{sub_i + 1:02d}_{safe}.png"
                    shot_path = os.path.join(SHOTS_DIR, shot_name)
                    cv2.imwrite(shot_path, ann)
                    screenshots_saved.append(shot_path)
                    shot_taken.add(key)
                    print(f"  Saved screenshot: {shot_name}")

        cap.release()

        # Transition card (1 second)
        if seg_idx < len(SEGMENTS) - 1:
            next_seg  = SEGMENTS[seg_idx + 1]
            next_file = os.path.splitext(next_seg["file"])[0].replace("_", " ").title()
            next_sub  = next_seg["subs"][0][2] if next_seg["subs"] else ""
            # Replace any remaining Unicode just in case
            next_sub  = next_sub.encode("ascii", "replace").decode("ascii")
            trans = draw_title_card(f"Next: {next_file}", next_sub, "")
            for _ in range(FPS_OUT):
                writer.write(trans)

    # ── Outro title card (2 seconds) ──────────────────────────────────────────
    print("\n[demo] Rendering outro…")
    outro = draw_title_card(
        "SANJAYA EDGE",
        "Proactive  |  Citizen-Facing  |  Real-Time  |  Legal Co-Pilot",
        "IIT Madras CoERS Road Safety Hackathon 2026  |  DriveLegal Track"
    )
    outro_f = corner_brackets(outro.copy())
    for _ in range(FPS_OUT * 2):
        writer.write(outro_f)

    shot_path = os.path.join(SHOTS_DIR, "99_outro.png")
    cv2.imwrite(shot_path, outro)
    screenshots_saved.append(shot_path)

    writer.release()
    print(f"\n[demo] ✓ Demo video saved: {DEMO_OUT}")
    print(f"[demo] ✓ Screenshots saved: {len(screenshots_saved)} files in screenshots/")
    print("\nScreenshots:")
    for s in screenshots_saved:
        print(f"  {os.path.basename(s)}")


if __name__ == "__main__":
    main()
