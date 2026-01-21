# Face Detector / Minor Guard (FastAPI)

This service accepts an image, **detects faces**, and performs an **age check**.  
If the photo likely contains a **minor (<18)** — the request is blocked.

Supported age-check providers:
- `opencv` — local (OpenCV DNN, no cloud)
- `aws` — AWS Rekognition
- `sightengine` — Sightengine
- `hive` — Hive

---

## Features

- **Request ID** per request (`X-Request-Id`), propagated to logs as `rid=...`.
- **Unified response format** for both success and errors.
- **Fail-closed** or **fail-open** behavior when a provider fails.
- **Face required**: if no face is detected, the request returns an error (cannot verify age).

---

## Run locally

### Install dependencies
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration (env vars)

#### Minimal for OpenCV
Create `.env` file in the project root.

Use `.env.example` as a template.

#### OpenCV tuning
```bash
OPENCV_MODEL_DIR=models/opencv
OPENCV_DOWNLOAD_MODELS=true
OPENCV_FACE_CONF_TH=0.7

# IMPORTANT: these are the model's FIXED buckets.
# Use exactly these strings:
# (0-3),(4-7),(8-12),(13-20),(21-32),(33-43),(44-53),(54-100)
OPENCV_BLOCK_BUCKETS='(0-3),(4-7),(8-12),(13-20)'
```

### Start the server

```bash
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

---

## OpenCV models

On first run, the `opencv` provider automatically downloads models into `models/opencv`.

If you ever end up with broken weights / HTML downloaded instead of real models, delete the folder:
```bash
rm -rf models/opencv
```

Then restart the service to re-download clean models.

---

## Request ID

- Client can send: `X-Request-Id: <your-id>`
- Service always returns `X-Request-Id` and includes `request_id` in JSON responses.
- Logs include `rid=<request_id>` for easy tracing.

---

## API

### Health
- `GET /healthz`

### Image check
- `POST /api/v1/check_image`
- `multipart/form-data`, file field name: `file`

Example:
```bash
curl -s -X POST \
  -F "file=@./photo.jpg" \
  http://127.0.0.1:8000/api/v1/check_image | jq
```

---

## Response codes

- **200 OK** — check passed
- **403 MINOR_DETECTED** — likely contains a minor
- **422 FACE_NOT_DETECTED** — no face detected (age cannot be verified)
- **503 AGE_CHECK_UNAVAILABLE** — provider is unavailable and fail-closed is enabled

---

## Unified response format

Success:
```json
{
  "ok": true,
  "request_id": "ef3adfc22947",
  "data": { "filename": "photo.jpg" },
  "minor_guard": {
    "provider": "opencv_caffe",
    "is_minor": false,
    "reasons": ["faces_detected=1", "face[0] age_bucket=(25-32) p=0.81"]
  }
}
```

Error:
```json
{
  "ok": false,
  "request_id": "ef3adfc22947",
  "data": {},
  "error": "FACE_NOT_DETECTED",
  "message": "No face detected in the image. Please upload a clear face photo.",
  "minor_guard": {
    "provider": "opencv_caffe",
    "is_minor": false,
    "reasons": ["no_faces_detected"]
  }
}
```

Notes:
- `request_id` matches the `X-Request-Id` header (generated if not provided).
- `minor_guard.reasons` is intentionally capped (keeps payload small).
