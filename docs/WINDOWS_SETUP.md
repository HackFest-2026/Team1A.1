# Windows + VS Code setup (Python 3.10)

These steps are for Windows x64 with Python 3.10 and Node.js 20.19 or newer.

## 0. Prerequisites

- Python 3.10 installed (`py -3.10 --version`)
- Node.js 20.19+ installed (`node --version`, `npm --version`)
- VS Code opened at the repository root: `aegis-cop-main` (the folder containing `backend` and `frontend`)

If `node`/`npm` are not recognized, install the Node.js LTS Windows installer from https://nodejs.org/ and fully restart VS Code.

## 1. Recreate the Python environment

Because an earlier install may have left a partially installed environment, close any terminals currently running the backend, then delete the `.venv` folder from the project root using File Explorer. Open a new VS Code terminal at the project root and run:

```cmd
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt -c backend\requirements.lock.txt
```

Install the optional video dependencies:

```cmd
.venv\Scripts\python.exe -m pip install -r backend\requirements-vision.txt
```

Do not use the old Linux/Python 3.12 pins or manually mix package versions. The dependency files in this project now use a Python 3.10-compatible baseline. If pip still reports a resolver error, copy the complete error section; don't randomly downgrade additional packages.

## 2. Install the frontend

Open a second VS Code terminal at the project root:

```cmd
cd frontend
npm ci
```

If `npm ci` reports that `package.json` and `package-lock.json` are out of sync, stop and share the full error rather than deleting the lock file.

## 3. Start the backend

Use a dedicated terminal:

```cmd
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Leave this terminal open. API documentation: http://127.0.0.1:8000/docs

## 4. Start the frontend

Use the second terminal:

```cmd
cd frontend
npm run dev
```

Open the local URL Vite prints, usually http://localhost:5173.

Keep both terminals open.

## 5. Run backend tests

Open a third terminal:

```cmd
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

## 6. Video Intelligence notes

- First model use may download `yolov8n.pt`, so internet access may be required.
- CPU inference works but may be slow.
- The model detects supported generic object classes. It does not identify hostile intent or provide validated naval/army threat detection.
- Video observations are unverified evidence. AIS/satellite fusion, GPS extraction from video, and automatic route-engine integration are not implemented.
- Don't use this prototype for real operational decisions.
