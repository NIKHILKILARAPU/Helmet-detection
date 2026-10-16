# TrafficGuard AI — Smart Helmet Detection & E-Challan Management System

TrafficGuard AI is a modern, lightweight, accessible web frontend designed for automated roadside helmet compliance monitoring, candidate violation triage, and human-verified e-challan draft preparation.

Built as an engineering final year project (B.Tech) and engineered to run with minimal memory and instant dev-server boot on everyday hardware (such as Intel Core i5 with 8 GB RAM).

---

## 🚦 System Architecture & Role Interfaces

The application features a single-page responsive interface equipped with a **Development Demo Mode Role Switcher** located in the top navigation bar and sidebar footer. This enables complete evaluation of all four project personas without requiring separate authentication servers during grading and live demonstrations:

```
[Camera Streams / Webcam] ──► [AI Inference Boundary] ──► [Candidate Detection Ingestion]
                                                                     │
       ┌─────────────────────────────────────────────────────────────┴────────────────────────┐
       ▼                                                                                      ▼
[1. Admin Dashboard]                                                               [2. Reviewer Desk]
- Enforcement KPI metrics & today scans                                            - Queue triage (Pending, Drafts, Rejected)
- Hourly & monthly SVG compliance trends                                           - Evidence viewer with bounding boxes overlay
- Registered Citizen & Vehicle directory                                            - Approve CHALLAN_DRAFT (No fine issued)
- Staff user role management                                                       - Reject with mandatory audit reason
- Real-time API & database health telemetry                                        - Immutable audit history timeline
       ▲                                                                                      ▲
       │                                                                                      │
[4. Registered-Person Portal]                                                      [3. Camera Operator View]
- Plain language, citizen-accessible design                                        - Live laptop webcam stream via MediaDevices
- Linked vehicle records (State Vahan DB)                                          - Clean stream lifecycle (stop on unmount)
- Observation notice history & evidence inspect                                     - Frame snapshot & candidate pipeline test
- Report Mismatch / dispute review submission                                      - Detection outcome panel & telemetry
```

### 1. 🛡️ Admin Dashboard
* **Real-time Overview:** Today's total scanned vehicles, safety candidates, pending reviews, approved drafts, and rejected false alerts.
* **Longitudinal Trends:** Responsive SVG hourly traffic distribution chart and 6-month enforcement trend breakdown.
* **Registered Citizen Directory:** Vahan database records matching verified citizens to two-wheelers, masked mobile contacts, and notification logs.
* **Personnel Access:** Staff role allocation across Enforcement Admins, Review Officers, and Camera Operators.
* **System Health Monitor:** Telemetry cards displaying latency and connectivity for FastAPI, MongoDB, YOLOv8 inference, and camera hardware.

### 2. 🔍 Reviewer / Management Interface
* **Candidate Queue:** Filterable queue supporting `Pending Review`, `Draft Created`, `Rejected`, and `All Cases`.
* **Evidence Inspection Deck:** High-resolution evidence viewer with toggleable AI bounding box overlays (`NO_HELMET`, `HELMET`, `RIDER`, `LICENSE_PLATE`), confidence scores, and multi-level zoom.
* **State Registration Association:** Displays verified vehicle plate and masked owner information.
* **Due-Process Draft Sanction:** Clicking **Approve Challan Draft** opens a legal confirmation modal creating a provisional `CHALLAN_DRAFT`. *It does not claim legal guilt or automatically trigger financial penalties.*
* **Rejection Audit Workflow:** Rejecting false positives (e.g. shadow contours, lighting glare) requires selecting a documented cause (`FALSE_DETECTION_SHADOW`, `COMPLIANT_HELMET_VERIFIED`, etc.) and adds an entry to the audit log.

### 3. 📹 Camera Operator Workstation
* **Webcam Integration:** Hardware-accelerated local camera stream using browser standard `navigator.mediaDevices.getUserMedia`.
* **Resource Friendly:** Camera stream is only activated upon explicit user consent and automatically disposes all tracks on exit or stop.
* **Snapshot & Pipeline Testing:** Allows live snapshot capture or simulation of network CCTV/IP camera streams.
* **AI Telemetry:** Candidate classification indicator (`NO_HELMET_CANDIDATE`, `HELMET_DETECTED`, `UNCERTAIN`) with confidence meters and thumbnail history.

### 4. 👤 Registered-Person Portal
* **Accessible & Plain Language:** Eliminates internal police jargon to provide clear status information for vehicle owners.
* **Observation Transparency:** Explains that candidate detections are provisional and subject to human officer verification.
* **Vehicle Association:** Displays registered two-wheelers linked to the citizen profile.
* **Dispute & Redressal:** Built-in **Report Mismatch** form enabling citizens to contest an incorrect vehicle/face match before any formal action is taken.

---

## 🎨 Visual Design System

Built strictly following traffic-safety design principles:
* **Primary Navy:** `#17324D` — Navigation, headings, and high-hierarchy controls
* **Action Blue:** `#2563EB` — Primary actions, selected states, and links
* **Safety Amber:** `#F59E0B` — Pending review candidates and caution indicators
* **Safety Green:** `#15803D` — Verified records, compliant helmets, and active systems
* **Safety Red:** `#DC2626` — Candidate violations, rejection audits, and critical errors
* **Page Canvas:** `#F5F7FA` | **Card Surfaces:** `#FFFFFF` | **Borders:** `#E2E8F0`

---

## 💻 Tech Stack & Performance

* **Framework:** React 19 + TypeScript (Strict verbatimModuleSyntax enabled)
* **Build Tool:** Vite 8 (Sub-2 second production builds, sub-300ms HMR)
* **Styling:** Tailwind CSS v4 via `@tailwindcss/vite`
* **Icons:** Lucide React (`lucide-react`)
* **Charts:** Zero-dependency SVG chart components (low memory footprint, zero canvas overhead)
* **Linter:** Oxlint (Static analysis across all components)

---

## 🚀 Quickstart & Running Instructions

### Prerequisites
* Node.js v18+ (tested on Node v22.19.0)
* npm v9+

### 1. Install Dependencies
```bash
npm install
```

### 2. Start Development Server
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### 3. Verify Code Quality & Type Checks
```bash
# Run lightning-fast linter
npm run lint

# Production build test
npm run build

# Preview production build locally
npm run preview
```

---

## 🧪 Testing the 4 Demo Personas

1. In the header bar or the bottom of the sidebar, find the **Switch Demo Role** selector.
2. Select **Admin Dashboard:**
   - Explore the top stat cards and toggle between *Today* and *Monthly* summaries.
   - Hover over the Hourly Distribution chart bars and Monthly Trend cards.
   - Switch tabs to *Registered Persons*, click **View Full Profile**, and inspect linked vehicles.
3. Select **Reviewer / Management:**
   - Select case `TG-2026-8941` from the pending queue.
   - Click **Overlay On / Off** on the evidence image to toggle the AI bounding box.
   - Click **Approve Challan Draft** to test the draft sanction modal and toast alert.
   - Select another case and test **Reject Candidate Case** with a reason.
4. Select **Camera Operator:**
   - Click **Start Camera** to activate your laptop webcam (browser will request webcam permission).
   - Click **Capture & Analyze Frame** to generate a snapshot and simulate the detection pipeline.
   - Observe the new candidate case getting ingested into the reviewer queue in real-time.
   - Click **Stop Stream** to release camera hardware.
5. Select **Registered-Person Portal:**
   - View citizen Aditya Sharma's linked Honda Activa record.
   - Click **View Evidence** on a past observation.
   - Click **Report Mismatch** to test the grievance submission modal.

---

## 🔌 Backend Integration Boundary (FastAPI & MongoDB)

The frontend contains a modular service layer located under `src/services/`:
* `api.ts`: Central `fetch` client reading `VITE_API_BASE_URL` with health-checking fallback.
* `violationsService.ts`: CRUD endpoints (`/api/v1/violations`, `/approve-draft`, `/reject`).
* `statsService.ts`: Telemetry and time-series endpoints (`/api/v1/stats/dashboard`).
* `personService.ts`: Registry search and mismatch dispute submission.
* `cameraService.ts`: Webcam hardware abstraction and frame ingestion.
* `healthService.ts`: Health check probe (`/api/v1/health`).

### Connecting to Python FastAPI Backend:
1. Create a `.env` file in the project root:
   ```env
   VITE_API_BASE_URL=http://localhost:8000/api/v1
   ```
2. When the FastAPI service is running, the frontend automatically detects connectivity and turns the top banner badge to **FastAPI Connected**. If offline, it falls back to the in-memory demo state without crashing.

---

## 🔒 Privacy & Legal Due-Process Guarantees

* **No Facial Recognition:** Riders are never matched or identified by facial appearance; identification strictly requires an authorized registration lookup against the vehicle number plate.
* **Provisional Drafts Only:** AI detections are treated as unverified candidates until verified by a designated human review officer.
* **Masked PII:** Phone numbers (`+91 98*** **412`) and sensitive identifiers are masked by default across all dashboards.
