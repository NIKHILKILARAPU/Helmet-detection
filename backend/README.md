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
```

---

## 🛠️ Database Initialization Utility

The database initialization utility connects to MongoDB, applies `$jsonSchema` validators, creates performance and constraint indexes, and seeds the baseline `system_settings` document.

### Run Database Initialization
From the `backend/` directory with your virtual environment activated:

```bash
# Full initialization (creates collections, validators, indexes, and default settings)
python -m app.db.init_db

# Verification mode (checks MongoDB connection and health only without writing changes)
python -m app.db.init_db --verify-only

# Override connection URI or database name via CLI flags
python -m app.db.init_db --uri "mongodb://127.0.0.1:27017" --db-name "helmet_challan_db"
```

### Expected Output (When MongoDB is Online)
```text
======================================================================
  TrafficGuard AI — Database Initialization & Health Utility
  Target URI:      mongodb://localhost:27017
  Target Database: helmet_challan_db
======================================================================

Initialization Summary:
  Database:        helmet_challan_db
  Collections:     11 processed
  Default Settings:seeded (or already_present)
  Status:          SUCCESS (Exit 0)
```

### Idempotency Guarantee
The initialization command is completely **idempotent**:
- It will **not** drop existing collections or delete existing records.
- If a collection exists, it updates the validator via `collMod`.
- It re-applies indexes safely without creating duplicate index entries.
- If the baseline `system_settings` document with `key: "default"` already exists, existing settings are preserved.

---

## 🧪 Running the Test Suite

The test suite covers schema validators, enum restrictions, numeric constraints, index definitions, connection failure recovery, and idempotency:

```bash
# From backend/ directory
pytest -v
```

### Test Suite Structure
- `tests/test_schemas.py`: Verifies schema presence, required fields, enum enforcement, and numeric bounds using `jsonschema`.
- `tests/test_indexes.py`: Validates uniqueness, compound descending indexes, partial unique filter on `challanDraftNumber`, and verifies absence of TTL indexes.
- `tests/test_connection.py`: Tests `MongoDBManager` lifecycle, timeout handling, connection failures, and health reporting.
- `tests/test_init_db.py`: Tests collection creation, `collMod` updates, index application, settings seeding, and idempotency using mock database instances.
- `tests/test_integration_mongo.py`: Live integration tests against an active MongoDB server. Skips automatically with a clear diagnostic notice if a live MongoDB instance is offline.

---

## 🔍 Troubleshooting MongoDB Connection

If `python -m app.db.init_db` fails with exit code 1:

1. **Verify MongoDB service is running:**
   - **Windows:** `Get-Service MongoDB` or `Start-Service MongoDB` (in Administrator PowerShell)
   - **Linux:** `sudo systemctl status mongod` or `sudo systemctl start mongod`
   - **macOS:** `brew services list` or `brew services start mongodb-community`
2. **Verify port listener:**
   - Run `netstat -an | findstr 27017` to confirm port 27017 is listening.
3. **Check connection string in `backend/.env`:**
   - For local development: `MONGO_URI=mongodb://localhost:27017`
   - For MongoDB Atlas: `MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority`
4. **Atlas IP Whitelist:**
   - If using MongoDB Atlas, ensure your current IP address is whitelisted under **Network Access** in the Atlas console.
