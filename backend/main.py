"""
Sanjaya Edge — AI Road Safety Co-Pilot
Stack: YOLOv8n + OpenCV HSV · Temporal light tracking · Optical-flow wrong-side · Multi-violation
"""
import cv2
import json
import asyncio
import base64
import os
import time
import numpy as np
import concurrent.futures
from collections import defaultdict, deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO

# ─── Device detection (CUDA / CPU) ───────────────────────────────────────────
try:
    import torch
    DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"
    USE_HALF = False  # keep False — half-precision causes empty detections on some GPUs
    if DEVICE == "cuda":
        print(f"[GPU] CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        print("[GPU] CUDA not found — running on CPU")
except ImportError:
    DEVICE   = "cpu"
    USE_HALF = False
    print("[GPU] torch not installed — CPU only")

# Thread pool for YOLO inference (keeps async event loop unblocked)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# ─── App setup ───────────────────────────────────────────────────────────────
app = FastAPI(title="Sanjaya Edge")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_base       = os.path.dirname(os.path.abspath(__file__))
_videos_dir = os.path.normpath(os.path.join(_base, "..", "Videos"))

# ─── Models ──────────────────────────────────────────────────────────────────
model = YOLO("yolov8n.pt")
model.to(DEVICE)

_helmet_model_path = os.path.join(_base, "helmet_model.pt")
helmet_model = YOLO(_helmet_model_path) if os.path.exists(_helmet_model_path) else None
if helmet_model:
    helmet_model.to(DEVICE)
print(f"[helmet] {'Custom model loaded' if helmet_model else 'helmet_model.pt not found — motorcycle proxy active'}")

# Warm up model so first real frame isn't slow
_warmup = np.zeros((320, 320, 3), dtype=np.uint8)
model(_warmup, verbose=False, imgsz=320, device=DEVICE)
print(f"[warmup] Model warmed up on {DEVICE}")

with open(os.path.join(_base, "rules.json"), "r", encoding="utf-8") as f:
    LEGAL_DB = json.load(f)

# ─── COCO class IDs ──────────────────────────────────────────────────────────
CLS_PERSON        = 0
CLS_BICYCLE       = 1
CLS_MOTORCYCLE    = 3
CLS_CAR           = 2
CLS_BUS           = 5
CLS_TRUCK         = 7
CLS_TRAFFIC_LIGHT = 9
VEHICLE_CLASSES   = {CLS_CAR, CLS_BUS, CLS_TRUCK, CLS_MOTORCYCLE}

# Custom helmet model class IDs
HM_HELMET = 0
HM_HEAD   = 1
HM_PERSON = 2

VIDEO_EXTENSIONS = {".mp4", ".webm", ".avi", ".mov", ".mkv"}

# ─── Video catalogue ─────────────────────────────────────────────────────────
_KNOWN = {
    "red_light_clear.mp4":    ("red_light",       "Red Light — Clear",       "red_light"),
    "no_helmet.webm":         ("no_helmet",        "Helmet Violation",        "helmet"),
    "red_light_india.webm":   ("red_light_india",  "Red Light — India",       "red_light"),
    "intersection_india.mp4": ("intersection",     "Indian Intersection",     "general"),
    "traffic_congestion.mp4": ("traffic_block",    "Traffic Congestion",      "general"),
}


def _infer_type(filename: str) -> str:
    n = filename.lower()
    if any(k in n for k in ("helmet", "hardhat", "hard_hat", "head")):
        return "helmet"
    if any(k in n for k in ("red_light", "redlight", "signal", "traffic_light")):
        return "red_light"
    if any(k in n for k in ("wrong", "wrongside", "contra")):
        return "wrong_side"
    if any(k in n for k in ("block", "jam", "congestion", "gridlock")):
        return "general"
    return "general"


def _build_catalogue() -> dict:
    cat = {}
    if not os.path.isdir(_videos_dir):
        return cat
    for fname in sorted(os.listdir(_videos_dir)):
        if os.path.splitext(fname)[1].lower() not in VIDEO_EXTENSIONS:
            continue
        path = os.path.join(_videos_dir, fname)
        if fname in _KNOWN:
            key, label, vtype = _KNOWN[fname]
        else:
            key   = os.path.splitext(fname)[0].lower().replace(" ", "_").replace("-", "_")
            label = os.path.splitext(fname)[0].replace("_", " ").replace("-", " ").title()
            vtype = _infer_type(fname)
        base_key, n = key, 1
        while key in cat:
            key = f"{base_key}_{n}"; n += 1
        cat[key] = {"path": path, "label": label, "vtype": vtype, "filename": fname}
    return cat


VIDEO_CATALOGUE: dict = _build_catalogue()


# ─── Encoding ─────────────────────────────────────────────────────────────────
def encode_jpeg(frame: np.ndarray, quality: int = 60) -> str:
    # Cap output width at 640px to reduce WebSocket payload
    h, w = frame.shape[:2]
    if w > 640:
        scale = 640.0 / w
        frame = cv2.resize(frame, (640, int(h * scale)), interpolation=cv2.INTER_LINEAR)
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf).decode("utf-8")


# ─── Resize frame for inference ───────────────────────────────────────────────
def resize_for_inference(frame: np.ndarray, max_w: int = 416) -> np.ndarray:
    h, w = frame.shape[:2]
    if w <= max_w:
        return frame
    scale = max_w / w
    return cv2.resize(frame, (max_w, int(h * scale)), interpolation=cv2.INTER_LINEAR)


# ─── Pre-processing ───────────────────────────────────────────────────────────
def enhance_night(frame: np.ndarray) -> np.ndarray:
    """CLAHE contrast boost for dark footage (Pizer et al., 1987)."""
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return cv2.cvtColor(cv2.merge([clahe.apply(l), a, b]), cv2.COLOR_LAB2BGR)


def _is_dark(frame: np.ndarray) -> bool:
    return float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))) < 60


# ─── Thread-safe YOLO inference helpers ──────────────────────────────────────
def _infer(m: YOLO, frame: np.ndarray, conf: float, imgsz: int = 320):
    """Blocking YOLO call — must be run inside executor, NOT in async loop."""
    return m(frame, verbose=False, conf=conf, device=DEVICE, imgsz=imgsz)


async def run_yolo(m: YOLO, frame: np.ndarray, conf: float, imgsz: int = 320):
    """Non-blocking wrapper: runs YOLO in thread pool so event loop stays free."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _infer, m, frame, conf, imgsz)


# ─── Temporal traffic light tracker ──────────────────────────────────────────
class LightStateTracker:
    """
    Requires consistent colour detection across N consecutive frames before
    committing to a state. Eliminates single-frame false positives.
    Inspired by: github.com/sovit-123/Traffic-Light-Detection-Using-YOLO-v3
    """
    def __init__(self, confirm_frames: int = 4):
        self._state   = "unknown"
        self._streak  = 0
        self._confirm = confirm_frames

    def update(self, raw_color: str) -> str:
        if raw_color == self._state:
            self._streak = min(self._streak + 1, 99)
        else:
            self._streak = 1
            self._state  = raw_color
        return self._state if self._streak >= self._confirm else "unknown"

    def confirmed_state(self) -> str:
        return self._state if self._streak >= self._confirm else "unknown"


# ─── Traffic light colour detection (HSV) ────────────────────────────────────
def get_light_color(frame: np.ndarray, box) -> str:
    x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
    h_box, w_box = y2 - y1, x2 - x1
    if h_box < 10 or w_box < 4 or (h_box / max(w_box, 1)) < 0.5:
        return "unknown"
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return "unknown"

    hsv  = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    area = max(h_box * w_box, 1)

    r1 = cv2.inRange(hsv, np.array([0,   100, 100]), np.array([12,  255, 255]))
    r2 = cv2.inRange(hsv, np.array([160, 100, 100]), np.array([180, 255, 255]))
    red_px    = cv2.countNonZero(r1) + cv2.countNonZero(r2)
    green_px  = cv2.countNonZero(cv2.inRange(hsv, np.array([35, 50, 60]),   np.array([90,  255, 255])))
    yellow_px = cv2.countNonZero(cv2.inRange(hsv, np.array([18, 100, 100]), np.array([38,  255, 255])))

    red_r, green_r, yellow_r = red_px / area, green_px / area, yellow_px / area

    # Use top-third / bottom-third brightness to distinguish lights in dark frames
    third = max(1, h_box // 3)
    top_v = float(np.mean(hsv[:third, :, 2]))
    mid_v = float(np.mean(hsv[third:2*third, :, 2]))
    bot_v = float(np.mean(hsv[2*third:, :, 2]))

    if green_r  > 0.06 or (bot_v > top_v + 25 and bot_v > mid_v + 10): return "green"
    if yellow_r > 0.06 or (mid_v > top_v + 20 and mid_v > bot_v + 10): return "yellow"
    if red_r    > 0.04 or (top_v > bot_v + 25 and top_v > mid_v + 10): return "red"

    return "unknown"


# ─── Vehicle in intersection zone ─────────────────────────────────────────────
def vehicle_in_zone(frame: np.ndarray, results,
                    y_frac=(0.30, 0.88)) -> tuple[bool, int, float]:
    H = frame.shape[0]
    zt, zb = int(H * y_frac[0]), int(H * y_frac[1])
    best_conf, best_cls = 0.0, -1
    for result in results:
        for box in result.boxes:
            cls  = int(box.cls[0])
            conf = float(box.conf[0])
            if cls not in VEHICLE_CLASSES or conf < 0.25:
                continue
            _, _, _, by2 = (int(v) for v in box.xyxy[0])
            if zt < by2 < zb and conf > best_conf:
                best_conf = conf; best_cls = cls
    return best_cls != -1, best_cls, best_conf


# ─── Traffic blocking — vectorised IoU cluster ────────────────────────────────
def detect_traffic_blocking(frame: np.ndarray, results,
                             min_vehicles: int = 6) -> tuple[bool, int]:
    """
    Vectorised pairwise overlap check (inspired by github.com/BrennoCaldato/traffic-density).
    Flags gridlock when ≥ min_vehicles form a dense cluster.
    """
    H, W = frame.shape[:2]
    zt, zb = int(H * 0.12), int(H * 0.92)
    zl, zr = int(W * 0.04), int(W * 0.96)

    boxes = []
    for result in results:
        for box in result.boxes:
            cls  = int(box.cls[0])
            conf = float(box.conf[0])
            if cls not in VEHICLE_CLASSES or conf < 0.22:
                continue
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            if zl < cx < zr and zt < cy < zb:
                boxes.append([x1, y1, x2, y2])

    n = len(boxes)
    if n < min_vehicles:
        return False, n

    pad = 25
    bs  = np.array(boxes, dtype=np.float32)
    ex1, ey1, ex2, ey2 = bs[:,0]-pad, bs[:,1]-pad, bs[:,2]+pad, bs[:,3]+pad

    cluster_pairs = 0
    for i in range(n):
        ix1 = np.maximum(ex1[i], ex1)
        iy1 = np.maximum(ey1[i], ey1)
        ix2 = np.minimum(ex2[i], ex2)
        iy2 = np.minimum(ey2[i], ey2)
        inter = np.maximum(ix2 - ix1, 0) * np.maximum(iy2 - iy1, 0)
        cluster_pairs += int(np.sum(inter[i+1:] > 0))

    return cluster_pairs >= max(n - 2, 2), n


# ─── Pedestrian in active lane ─────────────────────────────────────────────────
def pedestrian_in_lane(frame: np.ndarray, results) -> tuple[bool, float]:
    H, W = frame.shape[:2]
    zt, zb = int(H * 0.28), int(H * 0.85)
    zl, zr = int(W * 0.08), int(W * 0.92)
    best_conf = 0.0
    found = False
    for result in results:
        for box in result.boxes:
            if int(box.cls[0]) != CLS_PERSON:
                continue
            conf = float(box.conf[0])
            if conf < 0.38:
                continue
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            aspect = (y2 - y1) / max(x2 - x1, 1)
            if aspect < 1.2:
                continue
            if zl < cx < zr and zt < cy < zb:
                found = True
                best_conf = max(best_conf, conf)
    return found, best_conf


# ─── Optical-flow wrong-side detector ────────────────────────────────────────
class WrongSideDetector:
    """
    Estimates dominant vehicle flow direction using sparse Lucas-Kanade optical
    flow on tracked vehicle centres. Flags vehicles moving >45° against dominant flow.
    Inspired by: github.com/niconielsen32/ComputerVision opticalFlow examples.
    """
    def __init__(self, history: int = 20):
        self._centroids: deque = deque(maxlen=history)
        self._prev_gray  = None
        self._prev_pts   = None
        self._lk_params  = dict(
            winSize=(15, 15), maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )

    def _get_vehicle_centres(self, frame, results) -> np.ndarray:
        pts = []
        H, W = frame.shape[:2]
        for result in results:
            for box in result.boxes:
                if int(box.cls[0]) not in VEHICLE_CLASSES:
                    continue
                if float(box.conf[0]) < 0.30:
                    continue
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                if 0.05*W < cx < 0.95*W and 0.1*H < cy < 0.9*H:
                    pts.append([cx, cy])
        return np.array(pts, dtype=np.float32).reshape(-1, 1, 2) if pts else np.empty((0,1,2), np.float32)

    def update(self, frame: np.ndarray, results) -> tuple[bool, float]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cur_pts = self._get_vehicle_centres(frame, results)

        if self._prev_gray is None or self._prev_pts is None or len(self._prev_pts) == 0:
            self._prev_gray = gray
            self._prev_pts  = cur_pts
            return False, 0.0

        if len(self._prev_pts) < 2:
            self._prev_gray = gray
            self._prev_pts  = cur_pts
            return False, 0.0

        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            self._prev_gray, gray, self._prev_pts, None, **self._lk_params
        )

        good_prev = self._prev_pts[status == 1]
        good_next = next_pts[status == 1] if next_pts is not None else np.empty((0,2))

        self._prev_gray = gray
        self._prev_pts  = cur_pts

        if len(good_prev) < 2:
            return False, 0.0

        flow = (good_next - good_prev.reshape(-1, 2)).reshape(-1, 2)
        angles = np.arctan2(flow[:, 1], flow[:, 0]) * 180 / np.pi
        self._centroids.append(angles)

        if len(self._centroids) < 5:
            return False, 0.0

        all_angles = np.concatenate(list(self._centroids))
        if len(all_angles) < 4:
            return False, 0.0

        sin_m = np.mean(np.sin(np.radians(all_angles)))
        cos_m = np.mean(np.cos(np.radians(all_angles)))
        dom   = np.degrees(np.arctan2(sin_m, cos_m))

        if len(angles) == 0:
            return False, 0.0
        diffs = np.abs(((angles - dom + 180) % 360) - 180)
        against = np.sum(diffs > 140)
        if against > 0 and against / max(len(angles), 1) > 0.3:
            confidence = min(0.92, 0.55 + 0.08 * against)
            return True, confidence

        return False, 0.0


# ─── Main streaming coroutine ─────────────────────────────────────────────────
async def process_video(websocket: WebSocket, video_key: str):
    meta = VIDEO_CATALOGUE.get(video_key)
    if not meta:
        await websocket.send_text(json.dumps({"type": "ERROR", "msg": f"Unknown video: {video_key}"}))
        return

    path  = meta["path"]
    vtype = meta["vtype"]

    if not os.path.exists(path):
        await websocket.send_text(json.dumps({"type": "ERROR", "msg": f"File missing: {path}"}))
        return

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        await websocket.send_text(json.dumps({"type": "ERROR", "msg": f"Cannot open: {path}"}))
        return

    fps       = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_idx = 0

    last_alert_time:  dict[str, float] = {}
    last_alert_frame: dict[str, int]   = {}
    TIME_COOLDOWN  = 10.0
    FRAME_COOLDOWN = 150

    # Per-session state objects
    light_tracker        = LightStateTracker(confirm_frames=4)
    wrong_side_detector  = WrongSideDetector(history=25)
    current_light_color  = "unknown"

    # Run YOLO every Nth frame; reuse between
    SKIP          = 3   # increased from 2 → ~33% faster
    last_results  = None
    last_hm_results = None

    # Suppress alerts for first N frames (scene stabilisation)
    WARMUP_FRAMES = 30

    # Frame pacing — track wall time for accurate throttle
    FRAME_INTERVAL = 1.0 / fps
    last_frame_ts  = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_idx = 0
                light_tracker       = LightStateTracker(confirm_frames=4)
                wrong_side_detector = WrongSideDetector(history=25)
                continue

            frame_idx += 1
            now = asyncio.get_event_loop().time()

            is_dark  = _is_dark(frame)
            proc     = enhance_night(frame) if is_dark else frame
            conf_thr = 0.20 if is_dark else 0.25

            # ── Resize input for inference (much faster, tiny accuracy loss) ─
            proc_small = resize_for_inference(proc, max_w=416)

            # ── Run detection in thread executor (non-blocking) ──────────────
            run_full = (frame_idx % SKIP == 0) or last_results is None
            if run_full:
                use_helmet_model = (vtype in ("helmet", "general") and helmet_model is not None)
                if use_helmet_model:
                    last_hm_results = await run_yolo(helmet_model, proc_small, 0.32, imgsz=320)
                last_results = await run_yolo(model, proc_small, conf_thr, imgsz=320)

            results    = last_results
            hm_results = last_hm_results

            # ── Annotate frame — plot on the inference-size image ────────────
            # (boxes are in proc_small coordinates; plot() uses the same image)
            annotated = results[0].plot()

            # Overlay detection zone lines
            H, W = annotated.shape[:2]
            zt, zb = int(H * 0.30), int(H * 0.85)
            cv2.line(annotated, (0, zt), (W, zt), (0, 200, 200), 1)
            cv2.line(annotated, (0, zb), (W, zb), (0, 200, 200), 1)

            # Light indicator dot (top-right)
            lc_map = {"red": (0,0,255), "green": (0,255,0), "yellow": (0,220,255)}
            if current_light_color in lc_map:
                cv2.circle(annotated, (W - 28, 28), 14, lc_map[current_light_color], -1)
                cv2.circle(annotated, (W - 28, 28), 14, (255,255,255), 1)

            await websocket.send_text(json.dumps({
                "type":  "FRAME",
                "data":  encode_jpeg(annotated),
                "frame": frame_idx,
            }))

            # ── Cooldown helpers ─────────────────────────────────────────────
            def can_alert(vt: str) -> bool:
                if frame_idx < WARMUP_FRAMES:
                    return False
                t_ok = (now - last_alert_time.get(vt, 0)) > TIME_COOLDOWN
                f_ok = (frame_idx - last_alert_frame.get(vt, -9999)) > FRAME_COOLDOWN
                return t_ok and f_ok

            async def send_alert(vt: str, conf: float, desc: str = ""):
                last_alert_time[vt]  = now
                last_alert_frame[vt] = frame_idx
                rule = dict(LEGAL_DB[vt])
                if desc:
                    rule["msg"] = desc
                await websocket.send_text(json.dumps({
                    "type":          "ALERT",
                    "violation_key": vt,
                    "confidence":    round(conf, 1),
                    "rule":          rule,
                    "frame":         frame_idx,
                    "source":        "YOLOv8",
                }))

            # ═══════════════════════════════════════════════════════════════
            # DETECTOR 1 — Red Light  (with temporal state tracking)
            # ═══════════════════════════════════════════════════════════════
            if vtype in ("red_light", "general"):
                raw_color = "unknown"
                for result in results:
                    for box in result.boxes:
                        if int(box.cls[0]) != CLS_TRAFFIC_LIGHT:
                            continue
                        if float(box.conf[0]) < 0.25:
                            continue
                        c = get_light_color(proc_small, box)
                        if c != "unknown":
                            raw_color = c
                            break

                current_light_color = light_tracker.update(raw_color)

                if current_light_color == "red":
                    in_zone, vcls, vconf = vehicle_in_zone(proc_small, results)
                    if in_zone and can_alert("red_light"):
                        label = "Motorcycle" if vcls == CLS_MOTORCYCLE else "Vehicle"
                        await send_alert("red_light", round(vconf * 100, 1),
                                         f"{label} crossing confirmed red signal")
                    elif not in_zone and can_alert("red_light"):
                        await send_alert("red_light", 72.0)

            # ═══════════════════════════════════════════════════════════════
            # DETECTOR 2 — Helmet
            # ═══════════════════════════════════════════════════════════════
            if vtype in ("helmet", "general"):
                use_helmet_model = (helmet_model is not None and hm_results is not None)
                if use_helmet_model:
                    head_found = helmet_found = False
                    head_conf_max = 0.0
                    for result in hm_results:
                        for box in result.boxes:
                            cls  = int(box.cls[0])
                            conf = float(box.conf[0])
                            if cls == HM_HEAD and conf > 0.38:
                                head_found = True
                                head_conf_max = max(head_conf_max, conf)
                            elif cls == HM_HELMET and conf > 0.50:
                                helmet_found = True
                    if head_found and can_alert("no_helmet"):
                        await send_alert("no_helmet", round(head_conf_max * 100, 1),
                                         "Bare head detected — helmet violation confirmed")
                    elif helmet_found and not head_found and can_alert("helmet_ok"):
                        await send_alert("helmet_ok", 99.0,
                                         "Helmet worn — Section 129 MVA compliant")
                else:
                    for result in results:
                        for box in result.boxes:
                            if int(box.cls[0]) == CLS_MOTORCYCLE and float(box.conf[0]) > 0.28:
                                if can_alert("no_helmet"):
                                    await send_alert("no_helmet",
                                                     round(float(box.conf[0]) * 100, 1),
                                                     "Motorcyclist — helmet compliance unverified")

            # ═══════════════════════════════════════════════════════════════
            # DETECTOR 3 — Traffic Blocking
            # ═══════════════════════════════════════════════════════════════
            blocking, vehicle_count = detect_traffic_blocking(proc_small, results)
            if blocking and can_alert("traffic_blocking"):
                conf = min(95.0, 58.0 + vehicle_count * 4.5)
                await send_alert(
                    "traffic_blocking", conf,
                    f"{vehicle_count} vehicles clustered — possible intentional traffic obstruction"
                )

            # ═══════════════════════════════════════════════════════════════
            # DETECTOR 4 — Pedestrian in active lane
            # ═══════════════════════════════════════════════════════════════
            ped_found, ped_conf = pedestrian_in_lane(proc_small, results)
            if ped_found and can_alert("pedestrian_road"):
                await send_alert("pedestrian_road", round(ped_conf * 100, 1),
                                 "Pedestrian in active traffic lane — high collision risk")

            # ═══════════════════════════════════════════════════════════════
            # DETECTOR 5 — Wrong-side driving (optical flow)
            # ═══════════════════════════════════════════════════════════════
            if vtype in ("wrong_side", "general") and run_full:
                ws_flag, ws_conf = wrong_side_detector.update(proc_small, results)
                if ws_flag and can_alert("wrong_side"):
                    await send_alert("wrong_side", round(ws_conf * 100, 1),
                                     "Vehicle moving against traffic flow — wrong-side driving detected")

            # ── Frame pacing — yield to event loop, target video FPS ─────
            elapsed = asyncio.get_event_loop().time() - now
            sleep_t = max(0.0, FRAME_INTERVAL - elapsed)
            if sleep_t > 0:
                await asyncio.sleep(sleep_t)
            else:
                await asyncio.sleep(0)  # always yield at least once

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "ERROR", "msg": str(e)}))
        except Exception:
            pass
    finally:
        cap.release()


# ─── WebSocket endpoint ───────────────────────────────────────────────────────
@app.websocket("/ws/stream/{video_key}")
async def stream_endpoint(websocket: WebSocket, video_key: str):
    await websocket.accept()
    await process_video(websocket, video_key)


# ─── REST endpoints ───────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status":       "ok",
        "engine":       "YOLOv8n + OpenCV HSV + LK-Flow",
        "device":       DEVICE,
        "helmet_model": "custom (YOLOv8s)" if helmet_model else "motorcycle proxy",
        "videos":       len(VIDEO_CATALOGUE),
        "detectors":    ["red_light", "helmet", "traffic_blocking", "pedestrian_road", "wrong_side"],
    }


@app.get("/api/videos")
def get_videos():
    return [
        {
            "key":      key,
            "label":    meta["label"],
            "vtype":    meta["vtype"],
            "filename": meta["filename"],
        }
        for key, meta in VIDEO_CATALOGUE.items()
    ]


@app.get("/api/rules")
def get_rules():
    return LEGAL_DB
