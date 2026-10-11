# Video Intelligence add-on

This is an additive feature inside the existing React/Vite and FastAPI application. It does not replace the existing frontend, route engine, database, or incident workflow.

## What it does

- Accepts an uploaded video (150 MB maximum; common MP4/MOV/AVI/MKV/WEBM formats).
- Samples frames at a user-selected target rate.
- Runs a generic pretrained Ultralytics YOLO model on sampled frames and attempts ByteTrack IDs.
- Produces an annotated sampled-frame reel, class counts, timestamps, processing time, and a per-frame detection table.
- Writes an unverified `VIDEO_OBJECT_DETECTION` observation into the existing canonical evidence store.
- Accepts optional operator-supplied latitude/longitude and provenance notes.

## What it does not do

- It does not infer hostile intent or identify a vessel as hostile.
- It does not automatically create a threat, change a route, or dispatch a unit.
- It does not extract GPS from video or fuse AIS, satellite, radar, or live sensor feeds.
- It does not use a model trained specifically for naval/army threats.

## Install

From repository root, with the project's normal `.venv` already created and backend dependencies installed:

```bash
.venv/bin/python -m pip install -r backend/requirements-vision.txt
```

Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m pip install -r backend/requirements-vision.txt
```

PyTorch/Ultralytics may need a platform-specific install, particularly for GPU acceleration. The first run may download `yolov8n.pt`. Override with `AEGIS_YOLO_MODEL` to use a compatible local model path.

## Run

Terminal 1 (repository root):

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Terminal 2:

```bash
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run dev
```

Open `http://localhost:5173` and select **Video Intelligence**. The API status endpoint is `http://127.0.0.1:8000/api/vision/status`.

## Storage and caution

Original uploads are removed after processing. Annotated outputs persist under `data/vision_runs/`, which is gitignored; add retention cleanup and access control before deployment. The app currently has no authentication, so run locally on `127.0.0.1`, not exposed to a public network.
