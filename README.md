# TrafficGuard AI — Government Traffic Enforcement System

TrafficGuard AI is an official government-grade web application designed for municipal and state traffic police departments. It provides automated roadside helmet compliance monitoring, candidate violation triage, camera network management, and human-verified e-challan draft preparation.

Built for government traffic command centers and engineered to run with minimal memory and fast startup on standard department hardware (such as Intel Core i5 with 8 GB RAM).

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

## 💻 Tech Stack & Performance

* **Framework:** React 19 + TypeScript (Strict `verbatimModuleSyntax` enabled)
* **Build Tool:** Vite 8 (Sub-2 second production builds, sub-300ms HMR)
* **Styling:** Tailwind CSS v4 via `@tailwindcss/vite`
* **Icons:** Lucide React (`lucide-react`)
* **Charts:** Zero-dependency SVG chart components (low memory footprint, zero canvas overhead)
* **Linter:** Oxlint (0 errors, 0 warnings across all files)

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
# Run static linter
npm run lint

# Production build test
npm run build

# Preview production build locally
npm run preview
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
