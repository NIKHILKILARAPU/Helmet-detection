# TrafficGuard AI — Government Traffic Enforcement System

TrafficGuard AI is an official government-grade web application designed for municipal and state traffic police departments. It provides automated roadside helmet compliance monitoring, candidate violation triage, camera network management, and human-verified e-challan draft preparation.

Built for government traffic command centers and engineered to run with minimal memory and fast startup on standard department hardware (such as Intel Core i5 with 8 GB RAM).

---

## 📁 Repository Organization

The repository has been restructured into dedicated, self-contained directories separating the user interface, backend API service, AI model weights, and datasets:

```text
Helmet-detetection/
├── frontend/                     # React 19 + Vite 8 + TypeScript + Tailwind CSS UI
│   ├── public/                   # Static assets & icons
│   ├── src/
│   │   ├── assets/               # Branding images & illustrations
│   │   ├── components/           # Reusable UI components & common widgets
│   │   │   ├── common/           # Header, Sidebar, StatCard, StatusBadge, etc.
│   │   │   └── index.ts          # Barrel export
│   │   ├── context/              # AppContext state & role provider
│   │   ├── hooks/                # Custom React hooks (useCamera, useViolations)
│   │   ├── layouts/              # MainLayout wrapper (navigation + drawer + toasts)
│   │   ├── pages/                # Role-specific government enforcement views
│   │   │   ├── admin/            # Government Admin dashboard & policy management
│   │   │   ├── reviewer/         # Traffic Officer review queue & evidence triage
│   │   │   ├── operator/         # Camera Operator live stream & snapshot analysis
│   │   │   └── supervisor/       # Supervisory Officer compliance analytics & audit
│   │   ├── services/             # API services & mock fallback layer
│   │   ├── types/                # TypeScript interfaces & domain models
│   │   ├── utils/                # High-fidelity SVG mock evidence generator
│   │   ├── App.tsx               # Root application shell
│   │   └── main.tsx              # Application entrypoint
│   ├── .env.example              # Frontend environment template (VITE_API_BASE_URL)
│   ├── .oxlintrc.json            # Fast Rust-based linter configuration
│   ├── package.json              # Frontend npm dependencies and scripts
│   ├── tsconfig.json             # TypeScript project configuration
│   └── vite.config.ts            # Vite 8 + Tailwind CSS v4 build setup
│
├── backend/                      # Python FastAPI backend & AI inference service
│   ├── app/
│   │   ├── api/                  # REST endpoints (violations, stats, camera, health)
│   │   ├── models/               # YOLOv8 inference boundary & detection pipeline
│   │   └── config.py             # App settings & environment loader
│   ├── .env.example              # Backend environment template (DB, port, weights)
│   ├── main.py                   # FastAPI application entrypoint with CORS
│   ├── requirements.txt          # Python dependencies (FastAPI, Uvicorn, PyMongo, Ultralytics)
│   └── README.md                 # Backend setup and execution instructions
│
├── models/                       # AI model weights storage (kept outside frontend)
│   └── README.md                 # Instructions for placing yolov8n-traffic.pt
│
├── datasets/                     # Training & evaluation datasets (kept outside frontend)
│   └── README.md                 # Dataset format and annotation guidelines
│
├── .gitignore                    # Excludes node_modules, dist, venv, .env, and weights
├── package.json                  # Root convenience scripts (delegates to frontend)
└── README.md                     # Comprehensive project documentation
```

---

## 🚦 System Architecture & Government Role Interfaces

The application features a single-page responsive interface equipped with a **Development Demo Mode Role Switcher** located in the top navigation bar and sidebar footer. This enables complete evaluation of all four government enforcement roles:

```
[Camera Streams / Webcam] ──► [AI Edge Inference Boundary] ──► [Candidate Detection Ingestion]
                                                                        │
       ┌────────────────────────────────────────────────────────────────┴────────────────────────┐
       ▼                                                                                         ▼
[1. Government Admin]                                                               [2. Traffic Officer / Reviewer]
- Manages personnel, staff roles & permissions                                      - Queue triage (Pending, Drafts, Rejected)
- Camera Network Sources (RTSP, CCTV, Webcams)                                      - Evidence viewer with bounding boxes overlay
- State Vehicle Registry (Vahan DB records)                                         - Verifies authorized registration records
- Policy settings (confidence, penalties, retention)                                - Approves CHALLAN_DRAFT (No auto-fine)
- Infrastructure telemetry (FastAPI, MongoDB, YOLO)                                 - Rejection workflow with mandatory audit reasons
       ▲                                                                                         ▲
       │                                                                                         │
[4. Management / Supervisory Officer]                                               [3. Camera Operator]
- Executive compliance analytics & KPIs                                             - Live webcam stream via MediaDevices API
- Officer review productivity & shift tracking                                      - Clean stream lifecycle (disposed on exit)
- Camera network optical health & FPS telemetry                                     - Frame snapshot & candidate pipeline testing
- Immutable system & policy audit trail                                             - AI candidate classification panel
```

### 1. 🛡️ Government Admin
* **Enforcement Overview:** Shift scan totals, safety candidates, pending reviews, approved drafts, and false alert rejections.
* **Camera Network Sources:** Register, configure, and monitor roadside CCTV and IP cameras across city junctions.
* **Authorized Registration Records:** State transport registry showing vehicle owners, plate numbers, masked contacts, and dispatch logs. Facial recognition is explicitly prohibited.
* **Staff & Role Permissions:** Access management across Enforcement Admins, Review Officers, Camera Operators, and Supervisors.
* **Enforcement Policy Settings:** Interactive parameters for minimum confidence threshold, pillion non-compliance flagging, triple-riding rules, night review requirements, penalty amounts, and data retention windows.
* **System Health Monitor:** Telemetry for FastAPI, MongoDB, YOLOv8 inference, and camera hardware.

### 2. 🔍 Traffic Officer / Reviewer
* **Candidate Queue:** Filterable queue supporting `Pending Review`, `Draft Created`, `Rejected`, and `All Cases`.
* **Evidence Inspection Deck:** High-resolution evidence viewer with toggleable AI bounding box overlays (`NO_HELMET`, `HELMET`, `RIDER`, `LICENSE_PLATE`), confidence scores, and multi-level zoom.
* **State Registration Association:** Displays verified vehicle plate and masked owner information (`+91 98*** **412`).
* **Due-Process Draft Sanction:** Clicking **Approve Challan Draft** opens a legal confirmation modal creating a provisional `CHALLAN_DRAFT`. *It does not claim legal guilt or automatically trigger financial penalties.*
* **Rejection Audit Workflow:** Rejecting false positives (e.g. shadow contours, lighting glare) requires selecting a documented cause (`FALSE_DETECTION_SHADOW`, `COMPLIANT_HELMET_VERIFIED`, etc.) and records an entry in the audit log.

### 3. 📹 Camera Operator
* **Webcam Integration:** Hardware-accelerated local camera stream using browser standard `navigator.mediaDevices.getUserMedia`.
* **Resource Friendly:** Camera stream is only activated upon explicit operator consent and automatically disposes all tracks on exit or stop.
* **Snapshot & Pipeline Testing:** Allows live snapshot capture or simulation of network CCTV/IP camera streams.
* **AI Telemetry:** Candidate classification indicator (`NO_HELMET_CANDIDATE`, `HELMET_DETECTED`, `UNCERTAIN`) with confidence meters and thumbnail history.

### 4. 📊 Management / Supervisory Officer
* **Executive Analytics:** Overall city compliance rate (93.9%), sanction consensus ratio, estimated draft fine volume, and false positive suppression rate.
* **Officer Productivity & Shifts:** Reviews completed today, approval ratios, rejections, average review duration per case, and officer duty status (`ON_DUTY`, `BREAK`, `ON_LEAVE`).
* **Camera Network Performance:** Optical uptime, resolution, frame rate, and detection yield per junction.
* **System & Policy Audit Trail:** Filterable log capturing all policy changes, draft sanctions, camera modifications, and actor IPs.
* **Digest Export:** One-click export for supervisory compliance reports.

---

## 🎨 Visual Design System

Built strictly following government enforcement design standards:
* **Primary Navy:** `#17324D` — Navigation, headings, and high-hierarchy controls
* **Action Blue:** `#2563EB` — Primary actions, selected states, and links
* **Safety Amber:** `#F59E0B` — Pending review candidates and caution indicators
* **Safety Green:** `#15803D` — Verified records, compliant helmets, and active systems
* **Safety Red:** `#DC2626` — Candidate violations, rejection audits, and critical errors
* **Page Canvas:** `#F5F7FA` | **Card Surfaces:** `#FFFFFF` | **Borders:** `#E2E8F0`

---

## ⚡ Exact Run Commands

### Method A: From Repository Root (Convenience Scripts)

```bash
# 1. Install frontend dependencies
npm run install:frontend

# 2. Launch Vite dev server
npm run dev

# 3. Run linting & type checks
npm run lint
npm run build
```

### Method B: Directly Inside `frontend/`

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
# Server starts at http://localhost:5173

# Linting and build verification
npm run lint
npm run build
```

### Method C: Starting the Python FastAPI Backend (`backend/`)

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# Linux/macOS:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Copy environment template
copy .env.example .env

# Start FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
# API docs available at http://localhost:8000/docs
```

---

## ⚙️ Environment Variables

### Frontend (`frontend/.env`)
Create a `.env` file inside `frontend/` by copying `frontend/.env.example`:
```env
# Base URL for the FastAPI backend API
VITE_API_BASE_URL=http://localhost:8000/api/v1

# Application environment
VITE_APP_ENV=development
```
> **Security Rule**: Never prefix backend secrets or database credentials with `VITE_`. Any variable starting with `VITE_` is bundled into the client build.

### Backend (`backend/.env`)
Create a `.env` file inside `backend/` by copying `backend/.env.example`:
```env
MONGODB_URI=mongodb://localhost:27017
DATABASE_NAME=trafficguard_ai
MODEL_WEIGHTS_PATH=../models/yolov8n-traffic.pt
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## 🧪 Testing the 4 Government Roles

1. In the header bar or the bottom of the sidebar, find the **Switch Government Role** selector.
2. Select **Government Admin:**
   - Toggle between *Today* and *Monthly* enforcement overviews.
   - Switch to *Camera Sources* and click **Register Camera Source** to test adding an RTSP stream.
   - Switch to *Policy Settings*, adjust the AI confidence slider or fine amount, and click **Save & Apply Policy**.
3. Select **Traffic Officer / Reviewer:**
   - Select case `TG-2026-8941` from the pending queue.
   - Click **Overlay On / Off** on the evidence image to toggle the AI bounding box.
   - Click **Approve Challan Draft** to test the draft sanction modal and toast alert.
   - Select another case and test **Reject Candidate Case** with a reason.
4. Select **Camera Operator:**
   - Click **Start Camera** to activate your laptop webcam (browser will request webcam permission).
   - Click **Capture & Analyze Frame** to generate a snapshot and simulate the detection pipeline.
   - Observe the new candidate case getting ingested into the reviewer queue in real-time.
   - Click **Stop Stream** to release camera hardware.
5. Select **Supervisory Officer:**
   - Review executive KPIs (city compliance rate, draft fine volume).
   - Inspect the **Officer Productivity** table tracking review times and shifts.
   - Inspect the **Camera Performance** status cards.
   - Search the **System & Policy Audit Trail** for recent sanctions and settings changes.

---

## 🔒 Privacy & Legal Due-Process Guarantees

* **No Facial Recognition:** Riders are never matched or identified by facial appearance; identification strictly requires an authorized registration lookup against the vehicle number plate.
* **Provisional Drafts Only:** AI detections are treated as unverified candidates until verified by a designated human review officer.
* **Masked PII:** Phone numbers (`+91 98*** **412`) and sensitive identifiers are masked by default across all dashboards.
* **Full Audit Trail:** All administrative decisions, policy updates, and draft sanctions are recorded with timestamp, officer name, and origin IP.
