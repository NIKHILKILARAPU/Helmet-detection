# TrafficGuard AI — Python FastAPI Backend

Official backend service for TrafficGuard AI, providing database models, JSON Schema validation, index specifications, and REST APIs for roadside candidate violation triage, e-challan draft sanctioning, camera network configuration, and YOLOv8 inference boundaries.

---

## 🗄️ Database Architecture (Phase 1: MongoDB)

The database layer uses **MongoDB** with default database name `helmet_challan_db`.

### 1. Required Collections & Schemas

| Collection | Primary Purpose | Key Identifiers & Unique Indexes |
| :--- | :--- | :--- |
| `users` | Enforcement personnel & credentials | Unique `email`, unique `employeeId`, index on `(role, status)` |
| `cameras` | Roadside CCTV, IP camera & webcam sources | Indexes on `status`, `junction` |
| `violations` | Candidate detections & draft sanctions | Compound `(status, capturedAt)`, `(cameraId, capturedAt)`, `(violationType, capturedAt)`, `(personId, capturedAt)`, **Partial unique** on `challanDraftNumber` |
| `audit_logs` | Append-only tamper-evident audit log | Compound `(entityType, entityId, timestamp)`, `(actorUserId, timestamp)` |
| `persons` | Authorized transport registry records | Unique `personReference`, index on `identityStatus` |
| `vehicles` | Motor vehicle registration records | Unique `plateNumber` |
| `person_vehicles` | Vehicle-owner relationship records | Unique `(personId, vehicleId, relationshipType)` |
| `system_settings` | Algorithmic thresholds & policy rules | Unique `key` (baseline document: `key: "default"`) |
| `notifications` | Dispatch history logs (SMS, Email) | Compound `(personId, date)`, index on `status` |
| `officer_shifts` | Officer duty and shift tracking | Compound `(officerId, shiftStart)` |
| `model_runs` | Computer vision pipeline telemetry | Compound `(cameraId, processedAt)`, index on `status` |

### 2. Architecture & Data Principles
- **MongoDB `$jsonSchema` Validators:** Strictly enforces field presence, allowed enums, and numeric bounds (such as `confidence` between `0.0` and `1.0`, non-negative penalty amounts, and positive retention windows).
- **No TTL Indexes:** Data and evidence are never silently purged by automatic TTL expiration. Retention is governed exclusively by approved administrative policy.
- **Foreign Key Convention:** Inter-collection relationships use MongoDB `ObjectId` references (e.g. `violations.cameraId -> cameras._id`). Since MongoDB does not enforce cross-collection referential integrity at the database engine level, application-level referential checks are enforced during mutations.
- **UTC-Aware Timestamps:** All datetime fields (`capturedAt`, `timestamp`, `createdAt`, `updatedAt`) are stored as UTC-aware datetimes.
- **Privacy & PII Protection:** Facial recognition is strictly prohibited. Identity matching relies solely on authorized motor vehicle database lookups. Phone numbers are masked across dashboards.

---

## 🔐 Security & RBAC Architecture (Phase 2)

TrafficGuard AI enforces a strict, least-privilege Role-Based Access Control (RBAC) model. Access tokens are short-lived JSON Web Tokens (JWT) signed with HMAC-SHA256. Passwords are encrypted using bcrypt.

### 1. Role Permission Matrix

| Capability / Endpoint Category | `admin` | `reviewer` | `operator` | `supervisor` |
| :--- | :---: | :---: | :---: | :---: |
| **User & Staff Management** | Full | None | None | None |
| **System Settings & Policy Thresholds** | Full (Audited) | Read Only | None | Read Only |
| **Camera Configuration & Credential Management** | Full | Read Only | Ingest/Status | Read Only |
| **Violation Triage & Draft Approval / Rejection** | Read Only | Full (Atomic) | None | Read Only |
| **Roadside Candidate Ingestion (`POST /violations`)** | Allowed | None | Ingest | None |
| **Person & Vehicle Registry Mutations** | Full | Read Only | None | Read Only |
| **Audit Logs Inspection (`GET /audit`)** | Full | None | None | Full |
| **Operational & Telemetry Logging** | Allowed | Allowed | Log Shift/Run | Full Oversight |
| **Dashboard Aggregations & Analytics** | Full | Read Only | Read Only | Full |

> **Key Rule:** Supervisors hold managerial oversight but are strictly forbidden from approving/rejecting challans or modifying algorithm policy thresholds. Only designated `reviewer` officers can perform triage. Reviewer and actor identities are extracted exclusively from the authenticated JWT session—never accepted from request payloads.

### 2. Standardized API Response Envelopes

All endpoints return predictable, typed JSON responses:

- **Single Record / Mutation (`ApiResponse[T]`):**
  ```json
  {
    "success": true,
    "data": { ... },
    "message": "Operation completed successfully."
  }
  ```

- **Paginated List (`PaginatedResponse[T]`):**
  ```json
  {
    "success": true,
    "data": [ ... ],
    "total": 142,
    "page": 1,
    "pageSize": 25,
    "totalPages": 6
  }
  ```

- **Consistent Error Structure (`ErrorResponse`):**
  ```json
  {
    "success": false,
    "error": {
      "code": "ENTITY_NOT_FOUND",
      "message": "Violation case 'CASE-2026-99999' was not found.",
      "details": []
    }
  }
  ```

---

## 🚀 Setup & Execution

### 1. Create and Activate Virtual Environment
```bash
# Navigate to the backend directory
cd backend

# Create virtual environment
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# Linux / macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
# Windows:
copy .env.example .env
# Linux / macOS:
cp .env.example .env
```

Ensure the following variables are configured in `backend/.env`:
```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=helmet_challan_db
MONGO_CONNECT_TIMEOUT_MS=5000
MONGO_SERVER_SELECTION_TIMEOUT_MS=5000

JWT_SECRET_KEY=replace-with-a-very-secure-random-secret-key-at-least-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

---

## 🛠️ CLI Utilities

### 1. Database Initialization Utility
Connects to MongoDB, applies `$jsonSchema` validators, creates compound and unique indexes, and seeds baseline enforcement policies.

```bash
# Full idempotent initialization
python -m app.db.init_db

# Verification mode (read-only health probe)
python -m app.db.init_db --verify-only
```

### 2. Initial Admin Bootstrap Utility
To ensure zero default credentials and prevent public registration vulnerabilities, an initial administrative account must be provisioned via the secure CLI tool:

```bash
python -m app.core.bootstrap_admin --employee-id "EMP-ADMIN-001" --name "System Administrator" --email "admin@trafficguard.gov.in" --department "Traffic IT Division" --rank "Director"
```
You will be prompted securely for a strong password (minimum 8 characters).

---

## 🌐 Implemented API Endpoints (Phase 2)

All protected endpoints require the HTTP header: `Authorization: Bearer <access_token>`.

### 1. Health & Readiness Probes
- `GET /api/v1/health` — Full service and live MongoDB ping health check.
- `GET /api/v1/health/db` — Dedicated liveness/readiness probe (returns HTTP 200 when MongoDB is connected, HTTP 503 if unreachable).

### 2. Authentication & Identity
- `POST /api/v1/auth/login` — Authenticate with email and password; returns short-lived JWT token and user profile.
- `GET /api/v1/auth/me` — Retrieve authenticated actor profile, role, rank, and session context.

### 3. Violations & E-Challan Workflow
- `GET /api/v1/violations` — Paginated and filterable list of violations (supports `status`, `violationType`, `cameraId`, `plateNumber`, `minConfidence`, `dateFrom`, `dateTo`).
- `GET /api/v1/violations/{caseId}` — Full case detail with evidence images, vehicle details, linked owner, and audit trail.
- `POST /api/v1/violations` — Ingest candidate detection from roadside AI pipeline (HTTP 201 Created).
- `POST /api/v1/violations/{caseId}/approve-draft` — **Atomic** approval of pending review into an e-challan draft with sanction metadata and mandatory reviewer notes (HTTP 200). Protected against double-review race conditions.
- `POST /api/v1/violations/{caseId}/reject` — **Atomic** rejection of candidate detection with structured rejection reason code and notes.

### 4. Camera Network Management
- `GET /api/v1/cameras` — List all registered CCTV, IP camera, and webcam sources with redacted connection credentials.
- `GET /api/v1/cameras/{id}` — Retrieve camera status, heartbeat, and resolution.
- `POST /api/v1/cameras` — Register new traffic camera source (Admin only; HTTP 201).
- `PATCH /api/v1/cameras/{id}/status` — Update camera operational state (`ONLINE`, `STANDBY`, `DEGRADED`, `OFFLINE`).
- `PATCH /api/v1/cameras/{id}/config` — Update junction location, stream URL, resolution, or frame rate (Admin only; credentials sanitized in response).

### 5. Transport Registry (Persons & Vehicles)
- `GET /api/v1/persons` — Search authorized registration records.
- `GET /api/v1/persons/{id}` — Retrieve person details with masked mobile numbers.
- `POST /api/v1/persons` — Register new authorized person record (Admin only).
- `POST /api/v1/persons/{id}/dispute` — Log identity mismatch dispute.
- `GET /api/v1/vehicles` — Search vehicles by normalized plate number.
- `GET /api/v1/vehicles/{plate}` — Retrieve vehicle registration and linked owner.
- `POST /api/v1/vehicles` — Register vehicle record with automatic plate number normalization (`normalize_plate_number`).
- `POST /api/v1/vehicles/link` — Establish vehicle-owner relationship preventing duplicates.

### 6. System Settings & Policy Thresholds
- `GET /api/v1/settings` — Retrieve current detection thresholds (`minDetectionConfidence`, `minPlateConfidence`), fine amounts, and data retention windows.
- `PATCH /api/v1/settings` — Update policy parameters (Admin only; all changes automatically logged in the immutable audit log).

### 7. Operations & Telemetry
- `POST /api/v1/operations/shift` — Log officer duty status (`ON_DUTY`, `OFF_DUTY`, `ON_PATROL`, `BREAK`).
- `POST /api/v1/operations/model-run` — Log computer vision pipeline execution telemetry and processing latency.

### 8. Audit & Compliance
- `GET /api/v1/audit` — Query append-only audit trail filtered by `entityType`, `action`, or `entityId` (Admin and Supervisor only). **No update or delete endpoints exist.**

### 9. Management & Analytics
- `GET /api/v1/stats/dashboard` — Live MongoDB aggregation computing today's detections, violations count, pending cases, approved drafts, rejected counts, helmet compliance rate percentage, hourly traffic distribution, and monthly enforcement trends.

---

## 🏃 Running the Application

### Development Server
From the `backend/` directory:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Interactive OpenAPI documentation will be accessible at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 🧪 Running the Test Suite

The comprehensive test suite covers schema validators, indexing, connection resilience, JWT authentication, RBAC authorization, atomic review concurrency, credential sanitization, and live MongoDB integration:

```bash
# From backend/ directory
pytest -v
```

### Test Coverage Highlights
- **`test_api_auth.py`**: Authentication tokens, invalid passwords, expired tokens, role permission matrix enforcement, bootstrap CLI verification.
- **`test_api_violations.py`**: Filtered listing, candidate creation, draft sanctioning, input validation, 401/403/422 handling.
- **`test_concurrency_review.py`**: Concurrent review simulation verifying atomic `find_one_and_update` on `PENDING_REVIEW` prevents double approvals and conflicting state transitions.
- **`test_api_cameras.py`**: Registration, URL credential sanitization (`user:pass@` stripped from outputs), status updates.
- **`test_api_vehicles.py`**: Plate normalization, duplicate prevention, vehicle-person relationship linking.
- **`test_api_settings_and_audit.py`**: Settings mutation authorization, automated audit trail insertion, audit log immutability.
- **`test_api_health.py`**: Live MongoDB ping and readiness probes returning 200 when online and 503 when offline.
- **`test_schemas.py` & `test_indexes.py`**: MongoDB `$jsonSchema` and index structure verification.
- **`test_connection.py` & `test_init_db.py`**: Database manager lifecycle and idempotent initialization.
- **`test_integration_mongo.py`**: Real live MongoDB database operations.

---

## ⚠️ Limitations & Future Work (Phases 3+)
- **YOLOv8 Edge Inference Service**: Scheduled for Phase 3. Live video streaming, frame extraction, bounding box prediction, and plate OCR will feed into `POST /api/v1/violations`.
- **Payment Gateway / Government Portal Sync**: Approved challan drafts currently reside in `violations` collection with `CHALLAN_DRAFT_APPROVED` status awaiting official state treasury API dispatch.
- **SMS/Email Gateway Integration**: Notification records are staged in the `notifications` collection and require external SMS/Email gateway dispatchers in future phases.
