export type Role = "admin" | "verifier";

export type DocumentStatus = "processing" | "active" | "revoked" | "failed";

export type Verdict = "authentic" | "tampered" | "revoked" | "unknown" | "invalid";

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  organization: string | null;
  is_active: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface DocumentSummary {
  id: string;
  document_name: string;
  owner_id: string;
  subject: string | null;
  issuer: string | null;
  merkle_root: string;
  key_id: string | null;
  algorithm: string;
  status: DocumentStatus;
  page_count: number;
  fragment_count: number;
  grid_rows: number;
  grid_cols: number;
  revoked_reason: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface FragmentRecord {
  fragment_index: number;
  page_index: number;
  cell_index: number;
  row: number;
  col: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  page_width: number;
  page_height: number;
  fragment_hash: string;
  text_hash: string;
  raster_hash: string;
  char_count: number;
  text_preview: string;
}

export interface QrPayloadInfo {
  version: number;
  document_id: string;
  merkle_root: string;
  issued_at: string;
  signature: string;
  signature_preview: string;
  key_id: string;
  algorithm: string;
}

export interface DocumentDetail extends DocumentSummary {
  signature: string;
  owner_name: string | null;
  owner_email: string | null;
  fragments: FragmentRecord[];
  verification_count: number;
  last_verified_at: string | null;
  qr_payload: QrPayloadInfo | null;
}

export interface FragmentAnalysis {
  fragment_index: number;
  page_index: number;
  cell_index: number;
  status: "intact" | "modified" | "missing" | "added";
  reason: string;
  expected_hash: string | null;
  actual_hash: string | null;
  text_changed: boolean;
  visual_changed: boolean;
  marker_status: "valid" | "mismatch" | "absent";
  expected_preview: string;
  actual_preview: string;
  box: BoundingBox | null;
}

export interface BoundingBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  page_width: number;
  page_height: number;
  nx0: number;
  ny0: number;
  nx1: number;
  ny1: number;
}

export interface HeatmapRegion extends BoundingBox {
  page_index: number;
  cell_index: number;
  status: FragmentAnalysis["status"];
  severity: number;
  reason: string;
}

export interface TimelineStep {
  step: string;
  ok: boolean | null;
  detail: string;
  at: string;
}

export interface VerificationResult {
  log_id: string;
  result: Verdict;
  tamper_score: number;
  verified_at: string;
  duration_ms: number;
  file: { name: string; sha256: string; page_count: number };
  document: {
    id: string | null;
    name: string | null;
    status: string;
    issuer: string | null;
    subject: string | null;
    issued_at: string | null;
    page_count: number | null;
    fragment_count: number | null;
    registered: boolean;
  };
  qr: { found: boolean; payload: QrPayloadInfo | null; raw_count: number };
  manifest_present: boolean;
  baseline_source: string;
  signature: {
    valid: boolean;
    algorithm: string;
    key_id: string | null;
    signed_root: string;
    signature_preview: string;
  };
  merkle: {
    match: boolean;
    signed_root: string;
    recomputed_root: string;
    leaf_count: number;
    proof_demo: {
      fragment_index?: number;
      leaf_hash?: string;
      path?: { position: string; hash: string }[];
      issued_root?: string;
      root_matches_signed_root?: boolean;
      proof_valid?: boolean;
      is_tampered_fragment?: boolean;
    };
  };
  watermark: {
    valid: boolean;
    bit_error_rate: number;
    bits_checked: number;
    bits_matched: number;
    expected_prefix: string;
    recovered_prefix: string;
    tolerance: number;
    note?: string;
  };
  fragments: {
    total: number;
    intact: number;
    modified: number;
    missing: number;
    added: number;
    marker_issues: number;
    analysis: FragmentAnalysis[];
  };
  heatmap: HeatmapRegion[];
  revoked: boolean;
  revoked_reason: string | null;
  timeline: TimelineStep[];
}

export interface VerificationLog {
  id: string;
  document_id: string | null;
  claimed_document_id: string | null;
  verifier: string;
  source: string;
  result: Verdict;
  tamper_score: number;
  fragments_total: number;
  fragments_modified: number;
  signature_valid: boolean;
  merkle_match: boolean;
  watermark_valid: boolean;
  qr_found: boolean;
  file_name: string;
  file_sha256: string;
  timestamp: string;
}

export interface AuditEntry {
  id: string;
  action: string;
  user_id: string | null;
  user_email: string | null;
  entity_type: string | null;
  entity_id: string | null;
  detail: string;
  ip_address: string | null;
  timestamp: string;
}

export interface DashboardStats {
  totals: {
    documents: number;
    active: number;
    revoked: number;
    processing: number;
    failed: number;
    fragments: number;
    users: number;
    verification_requests: number;
    documents_verified_clean: number;
    documents_flagged: number;
    tampered_verifications: number;
    avg_tamper_score: number;
  };
  documents_by_status: Record<string, number>;
  verifications_by_result: Record<string, number>;
  series: {
    date: string;
    issued: number;
    authentic: number;
    tampered: number;
    revoked: number;
    unknown: number;
    invalid: number;
  }[];
  recent_verifications: {
    id: string;
    document_id: string | null;
    file_name: string;
    verifier: string;
    result: Verdict;
    tamper_score: number;
    fragments_modified: number;
    timestamp: string;
  }[];
  recent_activity: AuditEntry[];
  top_documents: {
    document_id: string;
    name: string;
    checks: number;
    avg_tamper_score: number;
    status: string;
  }[];
  window_days: number;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  actions?: string[];
}

export interface QrLookupResult {
  payload: QrPayloadInfo;
  signature_valid: boolean;
  registered: boolean;
  root_matches_register: boolean;
  verdict: "valid" | "invalid" | "revoked";
  note: string;
  document: {
    id: string;
    name: string;
    status: string;
    issuer: string | null;
    subject: string | null;
    issued_at: string;
    page_count: number;
    fragment_count: number;
    revoked_reason: string | null;
  } | null;
}
