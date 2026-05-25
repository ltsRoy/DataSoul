/**
 * DataSoul API Client
 * ====================
 * Centralized typed API client for all backend endpoints.
 * Backend runs on http://localhost:8000
 */

const API_BASE = "http://localhost:8000";

/* ─── Generic fetcher ─── */
async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const errorBody = await res.text().catch(() => "Unknown error");
    throw new Error(`API ${res.status}: ${errorBody}`);
  }
  return res.json();
}

/* ═══════════════════════════════════════════
   TYPE DEFINITIONS (match backend responses)
   ═══════════════════════════════════════════ */

export interface UploadResponse {
  session_id: string;
  filename: string;
  rows: number;
  cols: number;
  columns: string[];
  size_mb: number;
}

export interface ColumnProfile {
  name: string;
  dtype: string;
  missing: number;
  missing_pct: number;
  unique: number;
  unique_pct: number;
  cardinality: string;
  stats?: {
    mean: number;
    median: number;
    std: number;
    min: number;
    max: number;
    q1: number;
    q3: number;
    skewness: number;
    kurtosis: number;
  };
  outliers?: {
    count: number;
    pct: number;
    lower_bound: number;
    upper_bound: number;
  };
  distribution?: string;
  top_values?: Record<string, number>;
  mode?: string | null;
  mode_frequency?: number;
  issues?: string[];
}

export interface QualityDimension {
  score: number;
  weight: number;
}

export interface QualityScore {
  overall: number;
  grade: string;
  dimensions: Record<string, QualityDimension>;
}

export interface ProfileResponse {
  overview: {
    rows: number;
    cols: number;
    memory_mb: number;
    dtypes: Record<string, number>;
    total_missing: number;
    total_missing_pct: number;
    total_duplicates: number;
  };
  columns: ColumnProfile[];
  missing_summary: {
    columns_with_missing: number;
    total_cells_missing: number;
    total_cells: number;
    overall_missing_pct: number;
    by_column: {
      column: string;
      missing: number;
      missing_pct: number;
      severity: string;
    }[];
  };
  duplicates: {
    exact_duplicates: number;
    duplicate_pct: number;
    severity: string;
  };
  correlations: {
    pairs: {
      col1: string;
      col2: string;
      correlation: number;
      severity: string;
    }[];
    total_numeric_cols?: number;
  };
  quality_score: QualityScore;
  filename?: string;
  sector?: {
    sector_name: string;
    confidence: number;
    matched_columns: string[];
  };
}

export interface Threat {
  id: string;
  severity: "critical" | "warning" | "low";
  title: string;
  column: string;
  category: string;
  impact: string;
  confidence: number;
  actions: string[];
}

export interface ThreatsResponse {
  total: number;
  critical: number;
  warning: number;
  low: number;
  threats: Threat[];
}

export interface InsightsResponse {
  kpis: {
    column: string;
    type: string;
    total: number;
    mean: number;
    median: number;
    std: number;
    min: number;
    max: number;
    kpi_type?: string;
    formatted_total?: string;
  }[];
  distributions: {
    column: string;
    values: Record<string, number>;
    unique: number;
    mode: string | null;
  }[];
  anomalies: {
    column: string;
    extreme_count: number;
    extreme_pct: number;
    max_extreme: number;
    min_extreme: number;
    median_value: number;
  }[];
  recommendations: string[];
}

export interface StoryResponse {
  story: string;
  llm_powered?: boolean;
}

export interface TransformResponse {
  status: string;
  original_shape: number[];
  new_shape: number[];
  actions_applied: number;
  audit_trail: {
    action: string;
    column?: string;
    detail: string;
    rows_affected: number;
  }[];
}

export interface AutoCleanResponse {
  status: string;
  actions_applied: number;
  audit: {
    action: string;
    column?: string;
    detail: string;
    rows_affected: number;
    confidence: number;
  }[];
  original_shape: number[];
  cleaned_shape: number[];
}

export interface IterateResponse {
  iteration: number;
  cleaned_profile: ProfileResponse;
  cleaned_threats: ThreatsResponse;
  comparison: {
    quality_score: {
      before: number;
      after: number;
      change: number;
      grade_before: string;
      grade_after: string;
      improvement_pct: number;
    };
    shape: {
      before: number[];
      after: number[];
      rows_changed: number;
      cols_changed: number;
    };
    missing_data: {
      before_pct: number;
      after_pct: number;
      cells_fixed: number;
    };
    duplicates: {
      before: number;
      after: number;
      removed: number;
    };
    threats: {
      before: number;
      after: number;
      resolved: number;
      critical_before: number;
      critical_after: number;
      critical_resolved: number;
    };
    dimensions: Record<
      string,
      { before: number; after: number; change: number; improved: boolean }
    >;
    column_changes: {
      column: string;
      metric: string;
      before: number | string;
      after: number | string;
      improved: boolean;
    }[];
    narrative: string;
  };
  status: string;
  message: string;
}

export interface ChatResponse {
  question: string;
  answer: string;
  rag_augmented: boolean;
  llm_powered?: boolean;
}

export interface LLMStatusResponse {
  available: boolean;
  model: string | null;
  preferred_model: string;
  engine: string;
  model_size?: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  engine: string;
  rag_status: {
    is_ready: boolean;
    has_chromadb: boolean;
    total_documents: number;
  };
  active_sessions: number;
}

export interface TimelineResponse {
  audit_trail: {
    action: string;
    column?: string;
    detail: string;
    rows_affected: number;
  }[];
  original_shape: number[];
  current_shape: number[];
  iteration_count: number;
}

export interface ExportResponse {
  download_url: string;
  format: string;
  rows: number;
  cols: number;
}

/* ═══════════════════════════════════════════
   CSV CORRECTION TYPES
   ═══════════════════════════════════════════ */

export interface CorrectionSuggestion {
  column: string;
  old_value: string;
  new_value: string;
  count: number;
  confidence: number;
  reason: string;
  type: string;
}

export interface CorrectionAnalysis {
  columns_analyzed: number;
  issues_found: number;
  corrections: CorrectionSuggestion[];
  encoding_issues: {
    column: string;
    type: string;
    patterns: { pattern: string; replacement: string; occurrences: number }[];
    confidence: number;
    auto_fixable: boolean;
  }[];
  format_issues: {
    column: string;
    type: string;
    confidence: number;
    auto_fixable: boolean;
  }[];
  type_issues: {
    column: string;
    type: string;
    suggestion: string;
    confidence: number;
    auto_fixable: boolean;
  }[];
  category_merges: CorrectionSuggestion[];
  llm_powered: boolean;
}

export interface AutoCorrectResponse {
  status: string;
  corrections_applied: number;
  audit: {
    action: string;
    column: string;
    detail: string;
    rows_affected: number;
    confidence: number;
    source: string;
  }[];
  original_shape: number[];
  corrected_shape: number[];
  llm_powered: boolean;
}

/* ═══════════════════════════════════════════
   PREDICTION TYPES
   ═══════════════════════════════════════════ */

export interface PredictionResult {
  status: string;
  column: string;
  type: string;
  missing_count: number;
  model: string;
  train_score?: number;
  feature_importance?: Record<string, number>;
  predictions?: { index: number; predicted_value: number | string }[];
  stats?: Record<string, number>;
  predicted_distribution?: Record<string, number>;
  suggested_fill?: number | string;
  llm_explanation: string;
}

export interface TrendForecast {
  status: string;
  date_column: string;
  value_column: string;
  data_points: number;
  periods_forecast: number;
  trend: {
    direction: string;
    slope: number;
    daily_change: number;
    r_squared: number;
  };
  historical: {
    mean: number;
    std: number;
    min: number;
    max: number;
    latest: number;
  };
  forecast: number[];
  moving_average: number[];
  llm_narrative: string;
}

export interface AnomalyResult {
  status: string;
  column: string;
  total_values: number;
  anomalies_found: number;
  anomaly_pct: number;
  anomaly_values: number[];
  anomaly_indices: number[];
  stats: {
    mean: number;
    std: number;
    q1: number;
    q3: number;
    iqr: number;
    lower_fence: number;
    upper_fence: number;
  };
  model: string;
  llm_analysis?: string;
}

export interface FeatureSuggestion {
  type: string;
  source_column?: string;
  source_columns?: string[];
  new_feature?: string;
  new_features?: string[];
  formula?: string;
  reason: string;
  confidence: number;
  source?: string;
}

export interface FeatureSuggestionsResponse {
  status: string;
  suggestions: FeatureSuggestion[];
  numeric_columns: string[];
  categorical_columns: string[];
  correlations: { col1: string; col2: string; correlation: number }[];
  llm_powered: boolean;
}

/* ═══════════════════════════════════════════
   API METHODS
   ═══════════════════════════════════════════ */

/** Upload a CSV/XLSX file */
export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const errorBody = await res.text().catch(() => "Unknown error");
    throw new Error(`Upload failed (${res.status}): ${errorBody}`);
  }
  return res.json();
}

/** Load a demo dataset */
export async function loadDemo(
  datasetName: string
): Promise<UploadResponse> {
  return apiFetch<UploadResponse>(`/api/demo/${datasetName}`, {
    method: "POST",
  });
}

/** Get dataset profile */
export async function getProfile(
  sessionId: string
): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>(`/api/profile/${sessionId}`);
}

/** Get threat analysis */
export async function getThreats(
  sessionId: string
): Promise<ThreatsResponse> {
  return apiFetch<ThreatsResponse>(`/api/threats/${sessionId}`);
}

/** Get strategy recommendations */
export async function getStrategies(sessionId: string): Promise<unknown> {
  return apiFetch(`/api/strategies/${sessionId}`);
}

/** Get auto-generated insights */
export async function getInsights(
  sessionId: string
): Promise<InsightsResponse> {
  return apiFetch<InsightsResponse>(`/api/insights/${sessionId}`);
}

/** Get AI-generated executive narrative */
export async function getStory(
  sessionId: string
): Promise<StoryResponse> {
  return apiFetch<StoryResponse>(`/api/story/${sessionId}`);
}

/** Apply approved transformations */
export async function transformDataset(
  sessionId: string,
  approvedActions: { type: string; column?: string }[]
): Promise<TransformResponse> {
  return apiFetch<TransformResponse>(`/api/transform/${sessionId}`, {
    method: "POST",
    body: JSON.stringify({ approved_actions: approvedActions }),
  });
}

/** Auto-clean dataset */
export async function autoClean(
  sessionId: string
): Promise<AutoCleanResponse> {
  return apiFetch<AutoCleanResponse>(`/api/auto-clean/${sessionId}`, {
    method: "POST",
  });
}

/** Auto-clean + iterate (re-profile) */
export async function autoCleanAndIterate(
  sessionId: string
): Promise<{ cleaning: AutoCleanResponse; iteration: IterateResponse }> {
  return apiFetch(`/api/auto-clean-and-iterate/${sessionId}`, {
    method: "POST",
  });
}

/** Re-profile after cleaning */
export async function iterate(
  sessionId: string
): Promise<IterateResponse> {
  return apiFetch<IterateResponse>(`/api/iterate/${sessionId}`, {
    method: "POST",
  });
}

/** Chat with your data */
export async function chatWithData(
  sessionId: string,
  question: string
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>(`/api/chat/${sessionId}`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

/** Stream story generation via SSE — yields tokens in real-time */
export async function streamStory(
  sessionId: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE}/api/story/${sessionId}/stream`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }));
      onError(err.detail || "Stream failed");
      return;
    }
    const reader = response.body?.getReader();
    if (!reader) { onError("No stream reader"); return; }
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.token) onToken(data.token);
            if (data.done) { onDone(); return; }
            if (data.error) { onError(data.error); return; }
          } catch { /* skip malformed */ }
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err instanceof Error ? err.message : "Stream failed");
  }
}

/** Stream chat response via SSE */
export async function streamChat(
  sessionId: string,
  question: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE}/api/chat/${sessionId}/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }));
      onError(err.detail || "Stream failed");
      return;
    }
    const reader = response.body?.getReader();
    if (!reader) { onError("No stream reader"); return; }
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.token) onToken(data.token);
            if (data.done) { onDone(); return; }
            if (data.error) { onError(data.error); return; }
          } catch { /* skip */ }
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err instanceof Error ? err.message : "Stream failed");
  }
}

/** Get LLM engine status */
export async function getLLMStatus(): Promise<LLMStatusResponse> {
  return apiFetch<LLMStatusResponse>("/api/llm/status");
}

/** Warmup the LLM model */
export async function warmupLLM(): Promise<{ status: string; model?: string }> {
  return apiFetch("/api/llm/warmup", { method: "POST" });
}

/** Export dataset */
export async function exportDataset(
  sessionId: string,
  format: "csv" | "json" | "xlsx"
): Promise<ExportResponse> {
  return apiFetch<ExportResponse>(`/api/export/${sessionId}/${format}`);
}

/** Download an exported file */
export function getDownloadUrl(filename: string): string {
  return `${API_BASE}/api/download/${filename}`;
}

/** Get API health */
export async function getApiHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health");
}

/** Get timeline/audit trail */
export async function getTimeline(
  sessionId: string
): Promise<TimelineResponse> {
  return apiFetch<TimelineResponse>(`/api/timeline/${sessionId}`);
}

/* ═══════════════════════════════════════════
   INTEGRATION TYPES & METHODS
   ═══════════════════════════════════════════ */

export interface IntegrationStatus {
  name: string;
  display_name: string;
  icon: string;
  supports_import: boolean;
  supports_export: boolean;
  available: boolean;
  auth_method?: string;
  install_hint?: string;
}

export interface IntegrationsResponse {
  integrations: IntegrationStatus[];
}

export interface IntegrationImportResponse {
  session_id: string;
  filename: string;
  rows: number;
  cols: number;
  columns: string[];
}

export interface ColabExportResponse {
  download_url: string;
  format: string;
  filename: string;
  rows: number;
  cols: number;
}

export interface HuggingFaceExportResponse {
  status: string;
  repo_id: string;
  url: string;
  rows_pushed: number;
}

/** List all available integrations */
export async function getIntegrations(): Promise<IntegrationsResponse> {
  return apiFetch<IntegrationsResponse>("/api/integrations");
}

/** Import from Google Sheets */
export async function importGoogleSheets(
  sheetUrl: string, credentials: Record<string, unknown>, sheetName?: string
): Promise<IntegrationImportResponse> {
  return apiFetch<IntegrationImportResponse>("/api/import/google-sheets", {
    method: "POST",
    body: JSON.stringify({ sheet_url: sheetUrl, credentials, sheet_name: sheetName }),
  });
}

/** Import from data.gov.in */
export async function importDataGovIn(
  resourceId: string, apiKey: string, limit?: number
): Promise<IntegrationImportResponse> {
  return apiFetch<IntegrationImportResponse>("/api/import/data-gov-in", {
    method: "POST",
    body: JSON.stringify({ resource_id: resourceId, api_key: apiKey, limit: limit ?? 1000 }),
  });
}

/** Import from Kaggle */
export async function importKaggle(
  datasetSlug: string, credentials: Record<string, unknown>, filename?: string
): Promise<IntegrationImportResponse> {
  return apiFetch<IntegrationImportResponse>("/api/import/kaggle", {
    method: "POST",
    body: JSON.stringify({ dataset_slug: datasetSlug, credentials, filename }),
  });
}

/** Import from SQL */
export async function importSQL(
  connectionString: string, query?: string, table?: string
): Promise<IntegrationImportResponse> {
  return apiFetch<IntegrationImportResponse>("/api/import/sql", {
    method: "POST",
    body: JSON.stringify({ connection_string: connectionString, query, table }),
  });
}

/** Export to Google Sheets */
export async function exportToGoogleSheets(
  sessionId: string, sheetName: string, credentials: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return apiFetch("/api/export/" + sessionId + "/google-sheets", {
    method: "POST",
    body: JSON.stringify({ sheet_name: sheetName, credentials }),
  });
}

/** Export to Hugging Face */
export async function exportToHuggingFace(
  sessionId: string, repoName: string, token: string, isPrivate?: boolean
): Promise<HuggingFaceExportResponse> {
  return apiFetch<HuggingFaceExportResponse>("/api/export/" + sessionId + "/huggingface", {
    method: "POST",
    body: JSON.stringify({ repo_name: repoName, token, private: isPrivate ?? false }),
  });
}

/** Export as Colab notebook */
export async function exportColabNotebook(
  sessionId: string
): Promise<ColabExportResponse> {
  return apiFetch<ColabExportResponse>("/api/export/" + sessionId + "/colab-notebook", {
    method: "POST",
  });
}

/** Export to Kaggle */
export async function exportToKaggle(
  sessionId: string, datasetName: string, credentials: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return apiFetch("/api/export/" + sessionId + "/kaggle", {
    method: "POST",
    body: JSON.stringify({ dataset_name: datasetName, credentials }),
  });
}

/* ═══════════════════════════════════════════
   CSV CORRECTION METHODS
   ═══════════════════════════════════════════ */

/** Analyze dataset for corrections (no changes applied) */
export async function analyzeCorrections(
  sessionId: string
): Promise<CorrectionAnalysis> {
  return apiFetch<CorrectionAnalysis>(`/api/correct/${sessionId}/analyze`, {
    method: "POST",
  });
}

/** Auto-correct dataset with AI */
export async function autoCorrect(
  sessionId: string, threshold?: number
): Promise<AutoCorrectResponse> {
  return apiFetch<AutoCorrectResponse>(`/api/correct/${sessionId}`, {
    method: "POST",
    body: JSON.stringify({ threshold: threshold ?? 0.90 }),
  });
}

/** Apply user-approved corrections */
export async function applyCorrections(
  sessionId: string,
  corrections: { column: string; old_value: string; new_value: string }[]
): Promise<AutoCorrectResponse> {
  return apiFetch<AutoCorrectResponse>(`/api/correct/${sessionId}/apply`, {
    method: "POST",
    body: JSON.stringify({ corrections }),
  });
}

/* ═══════════════════════════════════════════
   PREDICTION METHODS
   ═══════════════════════════════════════════ */

/** Predict missing values using ML + LLM */
export async function predictMissing(
  sessionId: string, column: string
): Promise<PredictionResult> {
  return apiFetch<PredictionResult>(`/api/predict/${sessionId}`, {
    method: "POST",
    body: JSON.stringify({ column }),
  });
}

/** Forecast trends for a time-series column */
export async function forecastTrend(
  sessionId: string,
  dateColumn: string,
  valueColumn: string,
  periods?: number
): Promise<TrendForecast> {
  return apiFetch<TrendForecast>(`/api/predict/${sessionId}/trend`, {
    method: "POST",
    body: JSON.stringify({
      date_column: dateColumn,
      value_column: valueColumn,
      periods: periods ?? 10,
    }),
  });
}

/** Detect anomalies in a numeric column */
export async function detectAnomalies(
  sessionId: string, column: string
): Promise<AnomalyResult> {
  return apiFetch<AnomalyResult>(`/api/predict/${sessionId}/anomalies`, {
    method: "POST",
    body: JSON.stringify({ column }),
  });
}

/** Get feature engineering suggestions */
export async function suggestFeatures(
  sessionId: string
): Promise<FeatureSuggestionsResponse> {
  return apiFetch<FeatureSuggestionsResponse>(
    `/api/predict/${sessionId}/features`,
    { method: "POST" }
  );
}

// -- integration imports --

export async function importFromKaggle(
  datasetSlug: string,
  filename?: string,
  credentials?: { username: string; key: string }
): Promise<UploadResponse> {
  return apiFetch<UploadResponse>("/api/import/kaggle", {
    method: "POST",
    body: JSON.stringify({ dataset_slug: datasetSlug, filename, credentials }),
  });
}

export async function importFromGoogleSheets(
  sheetUrl: string,
  sheetName?: string
): Promise<UploadResponse> {
  return apiFetch<UploadResponse>("/api/import/google-sheets", {
    method: "POST",
    body: JSON.stringify({ sheet_url: sheetUrl, sheet_name: sheetName }),
  });
}

export async function importFromSQL(
  connectionString: string,
  queryOrTable: string,
  isTable?: boolean,
  limit?: number
): Promise<UploadResponse> {
  return apiFetch<UploadResponse>("/api/import/sql", {
    method: "POST",
    body: JSON.stringify({
      connection_string: connectionString,
      ...(isTable ? { table: queryOrTable } : { query: queryOrTable }),
      limit,
    }),
  });
}

export async function importFromDataGovIn(
  resourceId: string,
  apiKey: string,
  limit?: number
): Promise<UploadResponse> {
  return apiFetch<UploadResponse>("/api/import/data-gov-in", {
    method: "POST",
    body: JSON.stringify({ resource_id: resourceId, api_key: apiKey, limit }),
  });
}

/* ═══════════════════════════════════════════
   MCP SERVER INTEGRATION METHODS
   ═══════════════════════════════════════════ */

export interface AwesomeMCPServer {
  name: string;
  repo: string;
  description: string;
  category: string;
  language: string;
  scope: string;
  os: string[];
  templates?: {
    stdio?: { command: string; args: string[] };
    sse?: { url: string };
  };
}

export interface MCPConnectionResponse {
  status: string;
  connection_id: string;
  server_info: { name?: string; version?: string };
  capabilities: Record<string, any>;
  logs: string[];
}

export interface MCPDiscoveryDetails {
  connection_id: string;
  tools: { name: string; description?: string; inputSchema: Record<string, any> }[];
  resources: { uri: string; name: string; description?: string; mimeType?: string }[];
}

/** Get list of awesome MCP servers */
export async function getAwesomeMCPServers(): Promise<{ servers: AwesomeMCPServer[] }> {
  return apiFetch<{ servers: AwesomeMCPServer[] }>("/api/mcp/awesome");
}

/** Connect to an MCP server */
export async function connectMCPServer(config: {
  transport: "stdio" | "sse";
  command?: string;
  args?: string[];
  url?: string;
}): Promise<MCPConnectionResponse> {
  return apiFetch<MCPConnectionResponse>("/api/mcp/connect", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

/** Discover status and logs of connected MCP server */
export async function discoverMCPServer(connectionId: string): Promise<MCPConnectionResponse> {
  return apiFetch<MCPConnectionResponse>(`/api/mcp/discover/${connectionId}`);
}

/** Fetch tools and resources for an active MCP server */
export async function discoverMCPServerDetails(connectionId: string): Promise<MCPDiscoveryDetails> {
  return apiFetch<MCPDiscoveryDetails>(`/api/mcp/discover/${connectionId}/details`);
}

/** Call an MCP tool */
export async function callMCPTool(
  connectionId: string,
  name: string,
  argumentsVal: Record<string, any>
): Promise<any> {
  return apiFetch<any>(`/api/mcp/call-tool/${connectionId}`, {
    method: "POST",
    body: JSON.stringify({ name, arguments: argumentsVal }),
  });
}

/** Read an MCP resource */
export async function readMCPResource(connectionId: string, uri: string): Promise<any> {
  return apiFetch<any>(`/api/mcp/read-resource/${connectionId}`, {
    method: "POST",
    body: JSON.stringify({ uri }),
  });
}

/** Disconnect from an MCP server */
export async function disconnectMCPServer(connectionId: string): Promise<{ status: string; message: string }> {
  return apiFetch<{ status: string; message: string }>(`/api/mcp/disconnect/${connectionId}`, {
    method: "POST",
  });
}

/** Import data retrieved from an MCP server as a new DataSoul dataset session */
export async function importFromMCP(
  connectionId: string,
  sourceName: string,
  content: any
): Promise<UploadResponse> {
  return apiFetch<UploadResponse>("/api/import/mcp", {
    method: "POST",
    body: JSON.stringify({ connection_id: connectionId, source_name: sourceName, content }),
  });
}

