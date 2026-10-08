# API reference

Base URL `http://127.0.0.1:8000`, all routes prefixed `/api/v1` (except `/health`).
Interactive docs with request/response schemas: **http://127.0.0.1:8000/docs**

## Authentication

Bearer JWT in the `Authorization` header. Access tokens last 30 minutes; refresh tokens
7 days. The frontend refreshes silently on the first 401 and retries the request once —
see [`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts).

| Access level | Meaning |
| --- | --- |
| **public** | no token needed |
| **user** | any signed-in account |
| **admin** | `role = admin` only; returns 403 otherwise |
| **optional** | works without a token, but attributes the record to you if present |

---

## Auth

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | public | Self-registration. **Always creates a verifier**, even if the body asks for `admin`. |
| `POST` | `/auth/login` | public | Returns an access + refresh token pair and the user record. |
| `POST` | `/auth/refresh` | public | Exchanges a refresh token for a new pair. Rejects access tokens. |
| `GET` | `/auth/me` | user | The current account. Used to confirm a cached session on page load. |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"admin@docauth.dev","password":"Admin@12345"}'
```

## Documents (issuing)

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/documents` | admin | Upload one PDF and issue the protected version. Query: `subject`, `issuer`. Returns the full record including every fragment. |
| `POST` | `/documents/bulk` | admin | Several PDFs in one request; per-file failures are reported inline rather than failing the batch. |
| `POST` | `/documents/samples` | admin | Generates and protects a demo certificate and transcript. |
| `GET` | `/documents` | admin | Paginated register. Query: `search`, `status`, `page`, `page_size`. |
| `GET` | `/documents/{id}` | admin | One document with its fragments, verification count and QR payload. |
| `GET` | `/documents/{id}/download` | admin | The secured PDF — this is what you distribute. |
| `GET` | `/documents/{id}/original` | admin | The source file as uploaded. |
| `GET` | `/documents/{id}/qr` | admin | The QR stamp as a PNG. |
| `GET` | `/documents/{id}/pages/{n}` | admin | Page `n` of the secured PDF rendered to PNG. Query: `dpi` (50–200). |
| `POST` | `/documents/{id}/revoke` | admin | Body `{"reason": "…"}`. Verification then returns `revoked`. |
| `POST` | `/documents/{id}/reinstate` | admin | Lifts a revocation. |
| `DELETE` | `/documents/{id}` | admin | Removes the record, its fragments and its files. Prefer revocation. |
| `POST` | `/documents/{id}/tamper-sandbox` | admin | Returns a deliberately altered **copy** for testing detection. The issued file is untouched; the action is audited. |

Tamper sandbox body:

```json
{ "mode": "edit_text", "page_index": 0, "cell_index": 6, "replacement": "Second Class - Pass" }
```

`mode` is one of `edit_text`, `overlay_block`, `strip_watermark`, `replace_page`.
The response carries an `X-Tamper-Description` header describing what was changed.

## Verification

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/verify` | optional | **The main endpoint.** Multipart `file`, optional `document_id` and `source`. Runs the whole pipeline and returns the full report plus a `log_id`. |
| `POST` | `/verify/qr` | public | Body `{"raw": "<QR payload JSON>"}`. Checks signature and register status without the file. |
| `GET` | `/verify/logs` | public | Paginated history. Query: `result`, `document_id`, `page`, `page_size`. |
| `GET` | `/verify/logs/{id}` | public | A stored verification with its complete report. |
| `GET` | `/verify/logs/{id}/report` | public | The report as a printable PDF. |
| `GET` | `/verify/logs/{id}/pages/{n}` | public | Page `n` of the **submitted** file, rendered — what the tamper heatmap draws on. |
| `POST` | `/verify/logs/{id}/email` | public | Body `{"to": "…", "note": "…"}`. Needs SMTP configured, and says so plainly if it isn't. |
| `GET` | `/verify/public-key` | public | The authority's active public key, so signatures can be checked independently of this service. |
| `GET` | `/verify/documents/{id}` | public | Minimal status lookup by document ID. |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/verify -F "file=@document.pdf"
```

### Shape of a verification response

```jsonc
{
  "log_id": "…",
  "result": "tampered",          // authentic | tampered | invalid | revoked | unknown
  "tamper_score": 24.6,          // 0 = as issued, 100 = nothing verifiable survived
  "file":      { "name": "…", "sha256": "…", "page_count": 1 },
  "document":  { "id": "…", "registered": true, "status": "active", … },
  "qr":        { "found": true, "payload": { "merkle_root": "…", "signature": "…", … } },
  "signature": { "valid": true, "algorithm": "ES256", "key_id": "…" },
  "merkle":    { "match": false, "signed_root": "…", "recomputed_root": "…",
                 "proof_demo": { "path": [ { "position": "left", "hash": "…" } ], … } },
  "watermark": { "valid": true, "bit_error_rate": 0.0, "bits_matched": 128 },
  "fragments": { "total": 12, "intact": 11, "modified": 1, "missing": 0, "added": 0,
                 "marker_issues": 1, "analysis": [ /* one entry per fragment */ ] },
  "heatmap":   [ { "page_index": 0, "cell_index": 6, "status": "modified",
                   "severity": 1.0, "nx0": 0.0, "ny0": 0.33, "nx1": 0.5, "ny1": 0.5 } ],
  "timeline":  [ { "step": "QR extraction", "ok": true, "detail": "…" } ]
}
```

`heatmap` coordinates come in both PDF points and normalised `nx0…ny1` form, so the UI can
position overlay boxes as percentages regardless of the rendered image size.

## Dashboards and administration

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/dashboard/stats` | admin | Totals, per-status and per-verdict counts, a daily time series (`days`, 1–90), recent verifications and activity, most-checked documents. |
| `GET` | `/dashboard/tamper-hotspots` | admin | Which grid cells get altered most often across all failing verifications. |
| `GET` | `/audit-logs` | admin | Paginated audit trail. Query: `action`, `user_id`, `page`, `page_size`. |
| `GET` | `/users` | admin | All accounts. |
| `POST` | `/users` | admin | Create an account in either role. |
| `POST` | `/users/{id}/toggle-active` | admin | Enable/disable. Refuses to disable yourself or the last active admin. |
| `GET` | `/health` | public | Liveness plus the active fragment grid and which QR decoders are available. |

## Errors

Standard HTTP codes with a JSON `detail`. Notable ones: `401` bad or expired token,
`403` wrong role, `409` duplicate email or already-revoked document, `413` file over
`MAX_UPLOAD_MB`, `415` not a PDF, `422` the document could not be processed.
