# Garmin-First Implementation Plan: Phases 1 and 2
## Goal
Build the first working Garmin-first version of the activity battery checker using the official Garmin Connect Developer Program, starting on OAuth 1 as required by Garmin account setup, while designing the system so OAuth 2 migration is straightforward later.
Primary near-term outcome:
- users connect Garmin
- app receives Garmin activity notifications
- app ingests recent activity FIT files
- app parses FIT files for device/sensor and battery information
## Guiding Decisions
- Primary integration: Garmin Activity API
- Auth starting point: OAuth 1
- Future auth target: OAuth 2 PKCE after Garmin migration
- User identity model: persist Garmin `userId` as the stable user key from the beginning
- Delivery model: server-to-server with Garmin ping/pull or push
- Preferred file source: Garmin Activity Files callback URL
- Preferred parser: local FIT parsing logic, cleaned up and reused from `battery_checker.py`
- Product rule: process all device-originated activities; only skip virtual/manual/non-device-originated ones
- FIT file handling: process in-memory by default; debug flag to save FIT files to disk
- Persistence: SQLite for early development
- Runtime: local FastAPI app first, Lambda deployment later
## Why Garmin First
Garmin Activity API explicitly supports:
- activity summaries
- activity details
- raw activity files including FIT
Relevant Garmin metadata already supports better filtering than Strava:
- `activityType`
- `deviceName`
- `manual`
- `isWebUpload`
This is a better fit for:
- finding real device-recorded rides (outdoor and indoor trainer)
- avoiding purely virtual activities that lack real sensor data
- retrieving original FIT files officially
- extracting sensor and battery data reliably
## Phase 1: Foundation and Auth
### 1.1 Objectives
Set up the official Garmin integration foundation with OAuth 1, webhook endpoints, and data ingestion plumbing.
### 1.2 Deliverables
- Garmin integration design document in repo
- local/dev configuration model for Garmin credentials and endpoints
- OAuth 1 user registration/connect flow design
- webhook endpoint contract for:
  - activities
  - activity files
  - deregistrations
  - user permission changes
- user persistence model
- token persistence model
- basic pull processor that can receive ping notifications and call callback URLs
- local test harness for simulated Garmin ping payloads
### 1.3 Auth Model
Start with OAuth 1 because Garmin requires apps to begin there.
Implementation requirements:
- store Garmin consumer key and consumer secret securely
- support OAuth 1 user authorization/registration flow
- persist Garmin user linkage and token material
- immediately fetch and store Garmin `userId` after registration where possible
- treat `userId` as the canonical internal user key, not token values
Design for migration from day one:
- schema should support both OAuth 1 and OAuth 2 token shapes
- all downstream activity processing should key off `userId`
- no business logic should depend on OAuth 1 token format
### 1.4 Endpoint Strategy
Enable Garmin endpoints for:
- Activity summaries
- Activity files
- Deregistrations
- User permission changes
Recommended initial integration mode:
- Ping/Pull first
Reason:
- simpler to inspect and debug than full push payload ingestion
- compatible with Garmin tools and callbackURL flow
- good fit for early development
Rules:
- respond `200` quickly to Garmin notifications
- process callback URLs asynchronously
- never hold ping requests open while pulling Garmin data
### 1.5 User and Data Model
Create internal records for:
#### Users
- internal user id
- Garmin `userId`
- Garmin auth mode (`oauth1`, later `oauth2`)
- registration status
- granted permissions
- timestamps for connected/disconnected/permission changes
#### Tokens
- auth mode
- access token / token secret for OAuth 1 as applicable
- token metadata
- migration state
- last successful API use
- last known Garmin `userId`
#### Activities
- Garmin `activityId`
- Garmin `summaryId`
- Garmin `activityType`
- Garmin `deviceName`
- `manual`
- `isWebUpload` if available
- start time
- file type
- file callback receipt time
- processing status
### 1.6 Filtering Rules for Candidate Activities
Do not parse every activity blindly.
Initial candidate filter:
- prefer `fileType = FIT`
- require `manual = false`
- reject `isWebUpload = true` where available
- reject purely virtual activity types:
  - `VIRTUAL_RIDE`
  - `VIRTUAL_RUN`
  - other clearly virtual/simulated types
- **do NOT reject indoor activity types** like `INDOOR_CYCLING` — indoor trainer rides recorded on real Garmin devices (e.g., Edge 1040) with real sensors (e.g., Assioma Favero pedals, cadence sensors, Sterzo steering) contain valid battery data
- accept all cycling categories:
  - `CYCLING`
  - `ROAD_BIKING`
  - `GRAVEL_CYCLING`
  - `MOUNTAIN_BIKING`
  - `INDOOR_CYCLING`
- accept running and other activity types that use battery-bearing sensors

Note on virtual activities: the original plan excluded virtual rides based on the assumption that e.g. Zwift FIT files may not contain battery info. This has not been verified. If research shows that virtual platform FIT files do contain real sensor battery data (because the Garmin head unit still records paired sensors during a Zwift ride), this exclusion should be reconsidered. The real filter is: does the FIT file contain meaningful device/sensor battery fields? If yes, process it regardless of activity type.

Secondary heuristics:
- prefer activities with Garmin device names that look like real devices
- allow fallback parsing if metadata is incomplete
### 1.7 Phase 1 Implementation Tasks
1. Create project structure for Garmin integration modules
2. Add environment/config loading for Garmin credentials and callback base URL
3. Define persistence schema for users, tokens, permissions, and activities
4. Implement Garmin webhook receiver skeleton
5. Implement ping payload parser
6. Implement callback URL fetcher for Activity summaries and Activity Files
7. Implement logging and idempotency guards
8. Add local simulation fixtures for Garmin ping bodies
9. Document Garmin setup steps in repo
### 1.8 Phase 1 Exit Criteria
Phase 1 is complete when:
- a Garmin-connected test user can be registered
- Garmin can hit local/dev endpoints successfully
- app acknowledges notifications correctly
- app can pull activity summary data from callback URLs
- app can pull activity file metadata or file callback URLs
- app stores Garmin `userId` and activity records correctly
## Phase 2: FIT Ingestion and Battery Parsing
### 2.1 Objectives
Download Garmin FIT activity files, parse them, extract sensor/device battery information, and identify the latest relevant device-recorded activity (outdoor or indoor).
### 2.2 Deliverables
- reusable FIT parsing module extracted from `battery_checker.py`
- cleaned device/sensor normalization layer
- activity file downloader
- processing pipeline for activity file callbacks
- logic to identify latest sensor-bearing ride (outdoor or indoor)
- structured parsed output for sensors and battery state
- CLI or local endpoint to inspect parsed results
### 2.3 FIT File Retrieval Strategy
Use Garmin Activity Files callback URLs from the Activity API.
Important rules from Garmin docs:
- callback URL is valid for only 24 hours
- duplicate downloads are rejected with `410`
- files are available only via callbackURL flow, not generic ad hoc polling
Therefore:
- download activity files immediately after notification
- record download success/failure
- avoid retry storms
- cache processing outcome

### 2.3.1 FIT File Storage
Default: process FIT files in-memory only. Do not persist raw FIT files to disk.
Debug mode: when enabled via `SAVE_FIT_FILES=true` environment variable or `--save-fit-files` CLI flag, write downloaded FIT files to a configurable directory for offline inspection and parser development.
- debug files should be named with activity ID and timestamp for easy identification
- debug directory should be gitignored
### 2.4 Parser Refactor
Refactor `battery_checker.py` into shared logic without losing the existing CLI.
Target separation:
- `battery_parser.py`
  - FIT scan logic
  - device normalization
  - battery extraction
  - sensor classification
- `battery_checker.py`
  - CLI wrapper only
Parser cleanup tasks:
- remove sibling-path import hack for `fitdecode`
- package `fitdecode` as a normal dependency
- fix duplicate Garmin product map keys
- convert print-heavy parsing into structured return values
- classify devices consistently:
  - head unit
  - HR strap
  - power meter
  - radar
  - light
  - cadence sensor
  - speed sensor
  - unknown
### 2.5 Activity Selection Logic
Need to find activities that contain real sensor/device battery data, regardless of whether they are outdoor or indoor.
Selection algorithm:
1. inspect candidate activities newest-first
2. skip clearly virtual/manual/web-upload activities using Garmin metadata (see §1.6 note on virtual activity research)
3. download FIT for the best candidates
4. parse `device_info`
5. accept the first candidate that contains meaningful external sensor data or battery-bearing devices
6. if no candidate qualifies, fall back to latest non-virtual Garmin-originated activity and report reduced confidence
Signals that increase confidence:
- device-recorded activity (outdoor or indoor)
- Garmin head unit such as Edge device in FIT
- external ANT+/sensor entries in `device_info`
- battery fields present on HRM/power/radar/light/pedal devices
Signals that decrease confidence:
- virtual activity type (but see §1.6 — needs research)
- manual/web-upload flag
- no external devices in FIT
- no battery or sensor records at all
### 2.6 Parsed Output Model
For each processed FIT file, store:
- Garmin activity identifiers
- file metadata
- parser status
- list of detected devices
- normalized device classification
- manufacturer
- product / product_name
- serial number if present
- battery voltage
- battery status
- source type
- confidence flags for “real device-recorded sensor ride”
### 2.7 Phase 2 Implementation Tasks
1. Extract parsing logic from `battery_checker.py` into shared module
2. Add dependency management for `fitdecode`
3. Implement FIT file downloader from Garmin callback URL
4. Add immediate file processing pipeline
5. Build activity candidate scorer
6. Add structured JSON output for parsed devices
7. Add test coverage using local FIT samples
8. Validate against:
   - known outdoor Garmin ride
   - indoor trainer ride with real sensors (Edge + power meter + HRM etc.)
   - virtual ride if available (research whether FIT contains battery data)
   - activity with low battery sample
9. Add operator-facing logs for why activities were skipped
### 2.8 Testing Plan
Use three categories of tests:
#### Auth and webhook tests
- simulated Garmin ping payloads
- permission-change events
- deregistration events
#### Activity selection tests
- virtual ride skipped (pending research on whether virtual FIT files contain battery data)
- manual/web-upload skipped
- outdoor cycling chosen
- indoor cycling with real sensors chosen (not skipped)
- fallback behavior when no qualifying activity found
#### FIT parsing tests
- real outdoor FIT sample
- low battery sample
- sample with multiple external sensors
- sample with no battery info
### 2.9 Phase 2 Exit Criteria
Phase 2 is complete when:
- Garmin notification arrives
- app pulls the associated activity file
- app parses FIT successfully
- app identifies devices and battery fields correctly
- app can determine the latest useful Garmin-recorded ride (outdoor or indoor)
- results are available in structured form for later UI/notification work
## OAuth 1 -> OAuth 2 Migration Plan
This is not part of initial implementation, but Phase 1 and 2 must be migration-safe.
### Migration assumptions
- Garmin converts the app/account to support OAuth 2
- existing OAuth 1 users remain functional initially
- users can be exchanged individually to OAuth 2
- OAuth 1 tokens remain valid for 30 days after exchange
- new ping/push structure takes effect after OAuth 1 expiry
### Migration-safe design requirements
- persist Garmin `userId` for every user as early as possible
- abstract token access behind an auth provider interface
- separate:
  - notification ingestion
  - callback execution
  - token storage
  - user identity
- support multiple auth modes per app during transition
## Resolved Decisions
1. **Persistence:** SQLite for early development — zero setup, easy to inspect, migrate to Postgres later if needed
2. **Runtime:** local FastAPI app first — fast iteration on webhook/callback flow; Lambda deployment later
3. **FIT file storage:** in-memory processing by default; debug flag (`SAVE_FIT_FILES=true` / `--save-fit-files`) to save to disk for inspection
4. **Indoor activities:** process indoor trainer rides — real Garmin devices (Edge 1040, etc.) paired with real sensors (Assioma Favero pedals, HRM, cadence, Sterzo) record battery data on indoor rides just like outdoor ones

## Open Questions for Implementation
1. Whether to expose parsed battery results through a minimal web UI in Phase 2 or keep CLI/log output only
2. Whether Zwift/virtual platform FIT files recorded by a Garmin head unit contain battery data from paired sensors — needs research with real files before deciding whether to exclude virtual activity types entirely
## Recommended Immediate Next Step
Begin with a local FastAPI-based Garmin integration skeleton for:
- OAuth 1 plumbing
- Garmin ping endpoint
- callback fetching
- FIT download and parsing pipeline
This gives the easiest path to later Lambda deployment and OAuth 2 migration.
A couple of key notes from the docs that shaped this:
- Garmin Activity Files are official and FIT-capable, but callback URLs are single-use and expire in 24 hours: Activity_API-1.2.4.pdf
- Garmin production review requires real webhook handling and at least two real users, so we should design for that from the start: Activity_API-1.2.4.pdf, Health_API_1.2.3.pdf
- OAuth 1 to OAuth 2 migration requires storing userId as the real stable identity key before migration: OAuth2 Migration Guide.pdf
