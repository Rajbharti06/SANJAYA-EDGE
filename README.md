# SANJAYA EDGE — AI Road Safety Co-Pilot

> **IIT Madras CoERS Road Safety Hackathon 2026 · DriveLegal Track**

Sanjaya Edge is a real-time, citizen-facing AI legal co-pilot that detects road traffic violations from live video, explains the exact law section violated, and announces the applicable fine — all within milliseconds.

---

## What It Does

| Detector | Method | Law |
|---|---|---|
| 🚦 Red Light Jump | YOLOv8 + HSV temporal tracking (4-frame confirm) | MVA Section 119 |
| ⛑️ Helmet Violation | Custom YOLOv8 head/helmet classifier | MVA Section 129 |
| ↩️ Wrong-Side Driving | Lucas-Kanade optical flow (dominant direction) | MVA Section 184 |
| 🚧 Traffic Blocking | Vectorised IoU cluster detection (≥6 vehicles) | MVA 184 / IPC 283 |
| 🚶 Pedestrian in Lane | Aspect-ratio + zone filtering | MVA Section 283 |

Every detection triggers a **voice warning** (Web Speech API, `en-IN`) and a **detailed legal card** showing the fine for TN, MH, and KA states.

---

## Demo Videos

All test videos are in the `Videos/` folder:

| File | Scenario |
|---|---|
| `red_light_clear.mp4` | Vehicle crossing a red signal — clear daytime |
| `red_light_india.webm` | Indian urban intersection, red light jump |
| `no_helmet.webm` | Motorcyclist without helmet |
| `wrong_side_driving.mp4` | Wrong-side driving on a road |
| `intersection_india.mp4` | Mixed Indian intersection footage |
| `traffic_congestion.mp4` | High-density traffic blocking |

---

## Architecture

```
┌─────────────────────────────────┐     WebSocket (base64 JPEG + JSON)
│  BACKEND  FastAPI + Python      │ ─────────────────────────────────▶ ┌───────────────────────────┐
│  • YOLOv8n  (COCO, CUDA/CPU)   │                                     │  FRONTEND  React + Vite   │
│  • Custom helmet model          │ ◀───────────── WS connect ───────── │  • Live annotated feed    │
│  • OpenCV HSV light detection   │                                     │  • Compliance event log   │
│  • Lucas-Kanade optical flow    │                                     │  • Voice co-pilot (en-IN) │
│  • Thread-pool inference        │                                     │  • 5-metric stats strip   │
└─────────────────────────────────┘                                     └───────────────────────────┘
```

**Key performance choices:**
- YOLO runs in a `ThreadPoolExecutor` — the async event loop never blocks
- Input resized to 416px wide before inference (`imgsz=320`) — ~4× faster
- Frame skip = 3 (inference every 3rd frame, results reused between)
- Output capped at 640px / JPEG Q60 before WebSocket send
- Model warm-up on startup (no cold-start lag on first frame)

---

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Open the browser, select a scenario, and press **▶ START SCAN**.

---

## Requirements

```
Python ≥ 3.11
FastAPI · Uvicorn · Ultralytics YOLOv8 · OpenCV · NumPy
Node ≥ 18 · React · Vite · Tailwind CSS
CUDA (optional, auto-detected — falls back to CPU)
```

---

## Legal Database

`backend/rules.json` — all violations with:
- National fine + TN / MH / KA state-specific fines
- Exact MVA 1988 / IPC section
- Risk statement
- Severity level (CRITICAL / HIGH / SAFE)

---

## Project Structure

```
SANJAYA-EDGE/
├── backend/
│   ├── main.py          ← FastAPI server + all detectors
│   ├── rules.json       ← Legal DB (9 violation types)
│   ├── requirements.txt
│   └── yolov8n.pt       ← Base COCO model
├── frontend/
│   ├── src/
│   │   ├── App.jsx      ← Full dashboard UI
│   │   └── index.css    ← Design system
│   └── index.html
├── Videos/              ← Test footage
└── README.md
```

---

## Differentiator

Most traffic enforcement systems are **reactive** (police-operated, post-incident). Sanjaya Edge is **proactive and citizen-facing** — it explains *what law was broken*, *what the fine is*, and *which state rule applies*, in real time. This turns every dashcam into a legal co-pilot.

---

*Built for IIT Madras CoERS Road Safety Hackathon 2026 · DriveLegal Track*
