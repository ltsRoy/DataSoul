"use client";

import { useState, useCallback, useRef, Suspense, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Upload, FileSpreadsheet, FileText, X, CheckCircle2,
  Activity, ArrowLeft, Sparkles, Database, ChevronRight,
  AlertCircle, Loader2, FileUp, Table, Globe, Terminal,
  Plug, Play, RefreshCw, Eye, Search, Layers, Cpu, Code
} from "lucide-react";
import {
  uploadFile, loadDemo, importFromKaggle, importFromGoogleSheets,
  importFromSQL, importFromDataGovIn, getAwesomeMCPServers,
  connectMCPServer, discoverMCPServerDetails,
  callMCPTool, readMCPResource, disconnectMCPServer, importFromMCP,
  type UploadResponse, type AwesomeMCPServer
} from "../api";
import { useSession } from "../useSession";

/* ─── Sample datasets for demo ─── */
const SAMPLE_DATASETS = [
  {
    id: "retail",
    name: "Retail Sales Dataset",
    rows: "~5,000",
    cols: 12,
    sector: "Retail & E-Commerce",
    description: "Orders, products, customers, revenue with common retail data issues (missing values, duplicates, outliers, inconsistent casing)",
  },
];

/* ─── File type config ─── */
const ACCEPTED_TYPES: Record<string, { ext: string; color: string; icon: typeof FileSpreadsheet }> = {
  "text/csv": { ext: "CSV", color: "#22c55e", icon: FileSpreadsheet },
  "application/vnd.ms-excel": { ext: "XLS", color: "#f59e0b", icon: Table },
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": { ext: "XLSX", color: "#3b82f6", icon: Table },
};

/* ─── Animated variants ─── */
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.08, duration: 0.5, ease: [0.22, 1, 0.36, 1] as const }
  })
};

function UploadPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDemo = searchParams.get("demo") === "true";
  const { setSession } = useSession();
  
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStep, setUploadStep] = useState(0); // 0=idle, 1=uploading, 2=profiling, 3=done
  const [isUploading, setIsUploading] = useState(false);
  const [uploadComplete, setUploadComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [importInput, setImportInput] = useState("");
  const [activeImport, setActiveImport] = useState<string | null>(null);
  const [kaggleUsername, setKaggleUsername] = useState("");
  const [kaggleKey, setKaggleKey] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // --- SQL import state ---
  const [sqlConnString, setSqlConnString] = useState("sqlite:///data.db");
  const [sqlIsTable, setSqlIsTable] = useState(false);
  const [sqlLimit, setSqlLimit] = useState(1000);

  // --- Data.gov.in import state ---
  const [dataGovApiKey, setDataGovApiKey] = useState("");
  const [dataGovLimit, setDataGovLimit] = useState(1000);

  // --- MCP import & dashboard state ---
  const [mcpAwesomeServers, setMcpAwesomeServers] = useState<AwesomeMCPServer[]>([]);
  const [mcpSearch, setMcpSearch] = useState("");
  const [mcpCategory, setMcpCategory] = useState<string>("All");
  const [mcpTransport, setMcpTransport] = useState<"stdio" | "sse">("stdio");
  
  // Stdio connect inputs
  const [mcpCommand, setMcpCommand] = useState("npx");
  const [mcpArgsInput, setMcpArgsInput] = useState("");
  
  // SSE connect inputs
  const [mcpSseUrl, setMcpSseUrl] = useState("http://localhost:3001/sse");
  
  // Connection state
  const [mcpConnectionId, setMcpConnectionId] = useState<string | null>(null);
  const [mcpIsConnected, setMcpIsConnected] = useState(false);
  const [mcpConnecting, setMcpConnecting] = useState(false);
  const [mcpServerInfo, setMcpServerInfo] = useState<{ name?: string; version?: string }>({});
  const [mcpLogs, setMcpLogs] = useState<string[]>([]);
  const [mcpShowLogs, setMcpShowLogs] = useState(false);
  
  // Dynamic Explorer state
  const [mcpActiveTab, setMcpActiveTab] = useState<"tools" | "resources">("tools");
  const [mcpTools, setMcpTools] = useState<any[]>([]);
  const [mcpResources, setMcpResources] = useState<any[]>([]);
  
  const [mcpSelectedTool, setMcpSelectedTool] = useState<any | null>(null);
  const [mcpToolArguments, setMcpToolArguments] = useState<Record<string, any>>({});
  const [mcpSelectedResource, setMcpSelectedResource] = useState<any | null>(null);
  
  const [mcpExecutionResult, setMcpExecutionResult] = useState<any | null>(null);
  const [mcpExecutionError, setMcpExecutionError] = useState<string | null>(null);
  const [mcpExecuting, setMcpExecuting] = useState(false);
  
  const [mcpDataPreview, setMcpDataPreview] = useState<any[] | null>(null);
  const [mcpPreviewHeaders, setMcpPreviewHeaders] = useState<string[]>([]);
  const [mcpPreviewStatus, setMcpPreviewStatus] = useState<string | null>(null);
  const [mcpIsImporting, setMcpIsImporting] = useState(false);

  // Fetch awesome servers database on load
  useEffect(() => {
    async function loadAwesome() {
      try {
        const res = await getAwesomeMCPServers();
        setMcpAwesomeServers(res.servers || []);
      } catch (err) {
        console.error("Failed to load awesome MCP servers", err);
      }
    }
    loadAwesome();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  }, []);

  const handleFile = async (f: File) => {
    setFile(f);
    setError(null);
    setIsUploading(true);
    setUploadStep(1);

    try {
      // Real upload to backend
      setUploadStep(1); // uploading
      const result = await uploadFile(f);
      setUploadResult(result);
      setUploadStep(2); // profiling
      
      // Store session
      setSession(result.session_id, result.filename);
      
      // Brief pause for UX
      await new Promise(r => setTimeout(r, 800));
      setUploadStep(3);
      setUploadComplete(true);
      setIsUploading(false);

      // Redirect to health page
      setTimeout(() => {
        router.push(`/health?session=${result.session_id}`);
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Is the backend running on localhost:8000?");
      setIsUploading(false);
      setUploadStep(0);
    }
  };

  const handleDemoSelect = async (id: string) => {
    setError(null);
    setFile(new File(["demo"], `${id}_demo.csv`, { type: "text/csv" }));
    setIsUploading(true);
    setUploadStep(1);

    try {
      const result = await loadDemo(id);
      setUploadResult(result);
      setUploadStep(2);

      setSession(result.session_id, result.filename);

      await new Promise(r => setTimeout(r, 800));
      setUploadStep(3);
      setUploadComplete(true);
      setIsUploading(false);

      setTimeout(() => {
        router.push(`/health?session=${result.session_id}`);
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load demo. Is the backend running on localhost:8000?");
      setIsUploading(false);
      setUploadStep(0);
      setFile(null);
    }
  };

  const handleIntegrationImport = async () => {
    if (!importInput.trim() || !activeImport) return;
    
    // Validations for specific imports
    if (activeImport === "kaggle" && (!kaggleUsername.trim() || !kaggleKey.trim())) {
      setError("Please enter your Kaggle username and API key.");
      return;
    }
    if (activeImport === "sql" && (!sqlConnString.trim())) {
      setError("Please enter database connection string.");
      return;
    }
    if (activeImport === "data-gov-in" && (!dataGovApiKey.trim())) {
      setError("Please enter your data.gov.in API key.");
      return;
    }
    
    setError(null);
    setFile(new File(["import"], `${activeImport}_import.csv`, { type: "text/csv" }));
    setIsUploading(true);
    setUploadStep(1);

    try {
      let result: UploadResponse;
      if (activeImport === "kaggle") {
        result = await importFromKaggle(importInput.trim(), undefined, {
          username: kaggleUsername.trim(),
          key: kaggleKey.trim(),
        });
      } else if (activeImport === "google-sheets") {
        result = await importFromGoogleSheets(importInput.trim());
      } else if (activeImport === "sql") {
        result = await importFromSQL(sqlConnString.trim(), importInput.trim(), sqlIsTable, sqlLimit);
      } else if (activeImport === "data-gov-in") {
        result = await importFromDataGovIn(importInput.trim(), dataGovApiKey.trim(), dataGovLimit);
      } else {
        throw new Error("Integration not yet implemented");
      }
      setUploadResult(result);
      setUploadStep(2);
      setSession(result.session_id, result.filename);
      await new Promise(r => setTimeout(r, 800));
      setUploadStep(3);
      setUploadComplete(true);
      setIsUploading(false);
      setActiveImport(null);
      setImportInput("");
      setKaggleUsername("");
      setKaggleKey("");
      setTimeout(() => {
        router.push(`/health?session=${result.session_id}`);
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed. Check the slug/URL and try again.");
      setIsUploading(false);
      setUploadStep(0);
      setFile(null);
    }
  };

  // --- MCP Client Handlers ---
  
  const handleMCPConnect = async () => {
    setMcpConnecting(true);
    setError(null);
    setMcpExecutionResult(null);
    setMcpDataPreview(null);
    
    try {
      let args: string[] = [];
      if (mcpTransport === "stdio" && mcpArgsInput.trim()) {
        const matches = mcpArgsInput.trim().match(/(?:[^\s"]+|"[^"]*")+/g);
        if (matches) {
          args = matches.map(arg => arg.replace(/^"|"$/g, ""));
        }
      }
      
      const config = mcpTransport === "stdio"
        ? { transport: mcpTransport as "stdio", command: mcpCommand.trim(), args }
        : { transport: mcpTransport as "sse", url: mcpSseUrl.trim() };
        
      const res = await connectMCPServer(config);
      
      setMcpConnectionId(res.connection_id);
      setMcpIsConnected(true);
      setMcpServerInfo(res.server_info);
      setMcpLogs(res.logs || []);
      
      // Load details
      await refreshMCPDetails(res.connection_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect to MCP server.");
    } finally {
      setMcpConnecting(false);
    }
  };

  const refreshMCPDetails = async (connId: string) => {
    try {
      const details = await discoverMCPServerDetails(connId);
      setMcpTools(details.tools || []);
      setMcpResources(details.resources || []);
      setMcpSelectedTool(null);
      setMcpToolArguments({});
      setMcpSelectedResource(null);
    } catch (err) {
      console.error("Failed to discover MCP details", err);
    }
  };

  const handleMCPDisconnect = async () => {
    if (!mcpConnectionId) return;
    try {
      await disconnectMCPServer(mcpConnectionId);
    } catch (err) {
      console.error("Error disconnecting", err);
    } finally {
      setMcpConnectionId(null);
      setMcpIsConnected(false);
      setMcpServerInfo({});
      setMcpTools([]);
      setMcpResources([]);
      setMcpSelectedTool(null);
      setMcpSelectedResource(null);
      setMcpExecutionResult(null);
      setMcpDataPreview(null);
    }
  };

  const handleMCPExecuteTool = async () => {
    if (!mcpConnectionId || !mcpSelectedTool) return;
    setMcpExecuting(true);
    setMcpExecutionError(null);
    setMcpExecutionResult(null);
    setMcpDataPreview(null);
    setMcpPreviewStatus(null);
    
    try {
      const res = await callMCPTool(mcpConnectionId, mcpSelectedTool.name, mcpToolArguments);
      setMcpExecutionResult(res);
      parseMCPDataPreview(res, mcpSelectedTool.name);
    } catch (err) {
      setMcpExecutionError(err instanceof Error ? err.message : "Tool call failed");
    } finally {
      setMcpExecuting(false);
    }
  };

  const handleMCPReadResource = async (uri: string, name: string) => {
    if (!mcpConnectionId) return;
    setMcpExecuting(true);
    setMcpExecutionError(null);
    setMcpExecutionResult(null);
    setMcpDataPreview(null);
    setMcpPreviewStatus(null);
    
    try {
      const res = await readMCPResource(mcpConnectionId, uri);
      setMcpExecutionResult(res);
      parseMCPDataPreview(res, name);
    } catch (err) {
      setMcpExecutionError(err instanceof Error ? err.message : "Failed to read resource");
    } finally {
      setMcpExecuting(false);
    }
  };

  const parseMCPDataPreview = (result: any, sourceName: string) => {
    let textData = "";
    if (result.content && Array.isArray(result.content)) {
      const textItem = result.content.find((c: any) => c.type === "text");
      if (textItem) {
        textData = textItem.text;
      }
    } else if (typeof result === "string") {
      textData = result;
    } else if (typeof result === "object") {
      textData = JSON.stringify(result);
    }
    
    if (!textData) return;
    
    const cleanStr = textData.trim();
    let rows: any[] = [];
    
    if (cleanStr.startsWith("[") || cleanStr.startsWith("{")) {
      try {
        const parsed = JSON.parse(cleanStr);
        if (Array.isArray(parsed)) {
          rows = parsed;
        } else if (typeof parsed === "object") {
          for (const key of ["records", "data", "rows", "results", "items"]) {
            if (key in parsed && Array.isArray(parsed[key])) {
              rows = parsed[key];
              break;
            }
          }
          if (rows.length === 0) {
            rows = [parsed];
          }
        }
      } catch {
        // failed parse
      }
    }
    
    // CSV parse attempt
    if (rows.length === 0) {
      try {
        const lines = cleanStr.split("\n");
        if (lines.length > 1) {
          const headers = lines[0].split(",").map(h => h.trim());
          const records = [];
          for (let i = 1; i < Math.min(lines.length, 100); i++) {
            const line = lines[i].trim();
            if (line) {
              const cols = line.split(",").map(c => c.trim());
              const record: any = {};
              headers.forEach((h, idx) => {
                record[h] = cols[idx] || "";
              });
              records.push(record);
            }
          }
          if (records.length > 0) {
            rows = records;
          }
        }
      } catch {
        // failed csv
      }
    }
    
    if (rows.length > 0 && typeof rows[0] === "object") {
      const headers = Object.keys(rows[0]);
      setMcpPreviewHeaders(headers);
      setMcpDataPreview(rows.slice(0, 5));
      setMcpPreviewStatus(`Detected tabular layout. Parsed ${rows.length} records.`);
    } else {
      setMcpPreviewStatus("Parsed data is raw text/JSON. Direct import requires a tabular format.");
    }
  };

  const handleMCPImportData = async (sourceName: string) => {
    if (!mcpConnectionId || !mcpExecutionResult) return;
    setMcpIsImporting(true);
    setError(null);
    setFile(new File(["mcp"], `mcp_${sourceName}.csv`, { type: "text/csv" }));
    setIsUploading(true);
    setUploadStep(1);
    
    try {
      const result = await importFromMCP(mcpConnectionId, sourceName, mcpExecutionResult);
      setUploadResult(result);
      setUploadStep(2);
      setSession(result.session_id, result.filename);
      await new Promise(r => setTimeout(r, 800));
      setUploadStep(3);
      setUploadComplete(true);
      setIsUploading(false);
      setActiveImport(null);
      setMcpConnectionId(null);
      setMcpIsConnected(false);
      setMcpDataPreview(null);
      
      setTimeout(() => {
        router.push(`/health?session=${result.session_id}`);
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed. Could not parse DataFrame.");
      setIsUploading(false);
      setUploadStep(0);
      setFile(null);
    } finally {
      setMcpIsImporting(false);
    }
  };

  const prefillServerTemplate = (srv: AwesomeMCPServer) => {
    if (srv.templates?.stdio) {
      setMcpTransport("stdio");
      setMcpCommand(srv.templates.stdio.command);
      setMcpArgsInput(srv.templates.stdio.args.join(" "));
    } else if (srv.templates?.sse) {
      setMcpTransport("sse");
      setMcpSseUrl(srv.templates.sse.url);
    }
  };

  // Awesome catalog filtering
  const filteredServers = mcpAwesomeServers.filter(srv => {
    const matchesSearch = srv.name.toLowerCase().includes(mcpSearch.toLowerCase()) || 
                          srv.description.toLowerCase().includes(mcpSearch.toLowerCase());
    const matchesCategory = mcpCategory === "All" || srv.category === mcpCategory;
    return matchesSearch && matchesCategory;
  });

  const categories = ["All", "Databases & Storage", "Browser Automation", "Art, Design & Visuals", "Research & Bioinformatics", "Aggregators & Search"];

  const uploadProgress = uploadStep === 0 ? 0 : uploadStep === 1 ? 40 : uploadStep === 2 ? 75 : 100;

  return (
    <div className="min-h-screen pt-20 pb-12">
      {/* ─── Navbar ─── */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass" style={{ borderRadius: 0, borderTop: "none", borderLeft: "none", borderRight: "none" }}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "var(--gradient-primary)" }}>
              <Activity size={18} color="white" />
            </div>
            <span className="font-display font-bold text-lg">DataSoul</span>
          </a>
          <a href="/" className="btn-ghost text-sm flex items-center gap-2">
            <ArrowLeft size={16} />
            Back
          </a>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6">
        {/* ─── Header ─── */}
        <motion.div className="text-center mb-12" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <h1 className="font-display text-3xl md:text-5xl font-bold mb-3">
            {isDemo ? (
              <>Pick a <span className="gradient-text">Demo Dataset</span></>
            ) : (
              <>Upload Your <span className="gradient-text">Dataset</span></>
            )}
          </h1>
          <p className="text-[var(--text-secondary)] text-lg">
            {isDemo
              ? "Choose from pre-loaded datasets to explore DataSoul's capabilities"
              : "Drop your CSV or Excel file — DataSoul will do the rest"
            }
          </p>
        </motion.div>

        {/* ─── Error Banner ─── */}
        <AnimatePresence>
          {error && (
            <motion.div
              className="glass-card mb-6 flex items-start gap-3"
              style={{ background: "rgba(239,68,68,0.08)", borderColor: "rgba(239,68,68,0.2)" }}
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              <AlertCircle size={18} className="text-[var(--critical)] mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-[var(--critical)]">Integration Action Failed</p>
                <p className="text-xs text-[var(--text-secondary)] mt-1">{error}</p>
              </div>
              <button onClick={() => setError(null)} className="ml-auto text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <X size={16} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ─── Demo Datasets ─── */}
        {isDemo && !file && (
          <motion.div className="grid gap-4 mb-8" initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.1 } } }}>
            {SAMPLE_DATASETS.map((d, i) => (
              <motion.button
                key={d.id}
                className="glass-card text-left w-full flex items-center gap-4 md:gap-6"
                style={{ cursor: "pointer" }}
                onClick={() => handleDemoSelect(d.id)}
                variants={fadeUp}
                custom={i}
                whileHover={{ scale: 1.01, borderColor: "rgba(99,102,241,0.3)" }}
                whileTap={{ scale: 0.99 }}
              >
                <div className="w-10 h-10 rounded-lg bg-[var(--primary-light)] text-[var(--primary)] flex items-center justify-center flex-shrink-0"><Database size={20} /></div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold">{d.name}</h3>
                    <span className="badge-info">{d.sector}</span>
                  </div>
                  <p className="text-sm text-[var(--text-secondary)] mb-2">{d.description}</p>
                  <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
                    <span>{d.rows} rows</span>
                    <span>{d.cols} columns</span>
                  </div>
                </div>
                <ChevronRight size={20} className="text-[var(--text-muted)]" />
              </motion.button>
            ))}
          </motion.div>
        )}

        {/* ─── Dropzone ─── */}
        {!isDemo && !file && (
          <>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.5 }}>
            <div
              className={`dropzone ${isDragging ? "active" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xls,.xlsx"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
              <motion.div animate={{ y: isDragging ? -10 : 0 }} transition={{ type: "spring", stiffness: 300 }}>
                <div className="w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6" style={{ background: "var(--primary-glow)", border: "1px solid rgba(99,102,241,0.2)" }}>
                  <FileUp size={36} className="text-[var(--primary)]" />
                </div>
                <h3 className="font-display font-semibold text-xl mb-2">
                  {isDragging ? "Drop it here!" : "Drag & drop your file here"}
                </h3>
                <p className="text-[var(--text-secondary)] text-sm mb-4">or click to browse</p>
                <div className="flex items-center justify-center gap-3">
                  {Object.values(ACCEPTED_TYPES).map((t, i) => (
                    <span key={i} className="px-3 py-1 rounded-full text-xs font-medium" style={{ background: `${t.color}15`, color: t.color, border: `1px solid ${t.color}30` }}>
                      .{t.ext.toLowerCase()}
                    </span>
                  ))}
                </div>
              </motion.div>
            </div>
            
            {/* Or use demo */}
            <div className="text-center mt-6">
              <a href="/upload?demo=true" className="text-sm text-[var(--primary)] hover:underline flex items-center justify-center gap-1">
                <Sparkles size={14} />
                Or try a demo dataset instead
              </a>
            </div>
          </motion.div>

          {/* Integrations Grid */}
          <motion.div className="mt-10" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
            <h3 className="text-sm font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-4 flex items-center gap-2">
              <Globe size={14} /> Or import from
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[
                { id: "kaggle", name: "Kaggle", color: "#20BEFF", placeholder: "username/dataset-name or URL" },
                { id: "google-sheets", name: "Google Sheets", color: "#34a853", placeholder: "https://docs.google.com/spreadsheets/d/..." },
                { id: "sql", name: "SQL Database", color: "#f59e0b", placeholder: "sqlite:///data.db" },
                { id: "data-gov-in", name: "data.gov.in", color: "#FF6B35", placeholder: "Resource ID" },
                { id: "mcp", name: "MCP Server", color: "#a855f7", placeholder: "Model Context Protocol", isPremium: true }
              ].map((src) => (
                <button
                  key={src.id}
                  className={`glass-card text-center py-4 transition-all hover:scale-[1.02] relative overflow-hidden`}
                  style={{ 
                    cursor: "pointer", 
                    borderColor: src.isPremium ? "rgba(168,85,247,0.3)" : undefined,
                    boxShadow: src.isPremium ? "0 0 12px rgba(168,85,247,0.06)" : undefined
                  }}
                  onClick={() => { setActiveImport(src.id); setImportInput(""); setError(null); }}
                >
                  {src.isPremium && (
                    <div className="absolute top-0 right-0 bg-[#a855f7] text-white text-[8px] font-bold px-2 py-0.5 rounded-bl-md shadow">
                      MCP
                    </div>
                  )}
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center mx-auto mb-2" style={{ background: `${src.color}15`, border: `1px solid ${src.color}25` }}>
                    {src.id === "sql" ? <Terminal size={16} style={{ color: src.color }} /> : 
                     src.id === "mcp" ? <Plug size={16} style={{ color: src.color }} /> :
                     <Database size={16} style={{ color: src.color }} />}
                  </div>
                  <span className="text-xs font-semibold">{src.name}</span>
                </button>
              ))}
            </div>

            {/* Import Dialog Panel */}
            <AnimatePresence>
              {activeImport && activeImport !== "mcp" && (
                <motion.div
                  className="glass-card mt-4"
                  initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-semibold capitalize">
                      Import from {activeImport.replace("-", " ").replace("in", "in (India)")}
                    </h4>
                    <button onClick={() => { setActiveImport(null); setImportInput(""); }} className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                      <X size={16} />
                    </button>
                  </div>

                  {/* Kaggle Fields */}
                  {activeImport === "kaggle" && (
                    <div className="grid grid-cols-2 gap-2 mb-2">
                      <input
                        type="text"
                        value={kaggleUsername}
                        onChange={(e) => setKaggleUsername(e.target.value)}
                        placeholder="Kaggle username"
                        className="text-sm px-4 py-2.5 rounded-lg bg-[var(--glass-bg)] border border-[var(--glass-border)] text-[var(--text-primary)] outline-none focus:border-[var(--primary)] transition-colors"
                      />
                      <input
                        type="password"
                        value={kaggleKey}
                        onChange={(e) => setKaggleKey(e.target.value)}
                        placeholder="API key (from kaggle.json)"
                        className="text-sm px-4 py-2.5 rounded-lg bg-[var(--glass-bg)] border border-[var(--glass-border)] text-[var(--text-primary)] outline-none focus:border-[var(--primary)] transition-colors"
                      />
                    </div>
                  )}

                  {/* SQL Fields */}
                  {activeImport === "sql" && (
                    <div className="grid grid-cols-3 gap-2 mb-2">
                      <input
                        type="text"
                        value={sqlConnString}
                        onChange={(e) => setSqlConnString(e.target.value)}
                        placeholder="Connection string (sqlite:///data.db)"
                        className="col-span-2 text-sm px-4 py-2.5 rounded-lg bg-[var(--glass-bg)] border border-[var(--glass-border)] text-[var(--text-primary)] outline-none focus:border-[var(--primary)] transition-colors"
                      />
                      <div className="flex items-center gap-2 justify-center border border-[var(--glass-border)] rounded-lg text-sm bg-[var(--glass-bg)]">
                        <input
                          type="checkbox"
                          id="sqlIsTable"
                          checked={sqlIsTable}
                          onChange={(e) => setSqlIsTable(e.target.checked)}
                          className="w-4 h-4 accent-[var(--primary)]"
                        />
                        <label htmlFor="sqlIsTable" className="cursor-pointer font-medium text-xs">Table instead of Query</label>
                      </div>
                    </div>
                  )}

                  {/* data.gov.in Fields */}
                  {activeImport === "data-gov-in" && (
                    <div className="grid grid-cols-2 gap-2 mb-2">
                      <input
                        type="password"
                        value={dataGovApiKey}
                        onChange={(e) => setDataGovApiKey(e.target.value)}
                        placeholder="API Key (from data.gov.in)"
                        className="text-sm px-4 py-2.5 rounded-lg bg-[var(--glass-bg)] border border-[var(--glass-border)] text-[var(--text-primary)] outline-none focus:border-[var(--primary)] transition-colors"
                      />
                      <input
                        type="number"
                        value={dataGovLimit}
                        onChange={(e) => setDataGovLimit(parseInt(e.target.value) || 1000)}
                        placeholder="Limit records (default 1000)"
                        className="text-sm px-4 py-2.5 rounded-lg bg-[var(--glass-bg)] border border-[var(--glass-border)] text-[var(--text-primary)] outline-none focus:border-[var(--primary)] transition-colors"
                      />
                    </div>
                  )}

                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={importInput}
                      onChange={(e) => setImportInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleIntegrationImport()}
                      placeholder={
                        activeImport === "kaggle" ? "Dataset slug (e.g. owner/dataset) or URL" :
                        activeImport === "google-sheets" ? "Paste Google Sheet URL..." :
                        activeImport === "sql" ? (sqlIsTable ? "Table name (e.g. users)" : "SQL Query (SELECT * FROM...)") :
                        "Resource ID (e.g., 5c21b072-...)"
                      }
                      className="flex-1 text-sm px-4 py-2.5 rounded-lg bg-[var(--glass-bg)] border border-[var(--glass-border)] text-[var(--text-primary)] outline-none focus:border-[var(--primary)] transition-colors"
                    />
                    <button
                      onClick={handleIntegrationImport}
                      disabled={!importInput.trim() || isUploading}
                      className="btn-primary text-sm px-5"
                    >
                      {isUploading ? <Loader2 size={16} className="animate-spin" /> : "Import"}
                    </button>
                  </div>

                  <p className="text-xs text-[var(--text-muted)] mt-2">
                    {activeImport === "kaggle" && "Enter Kaggle details. Retrieve tokens from kaggle.com -> Account Settings."}
                    {activeImport === "google-sheets" && "Paste public sheet link. The sheet must be shared as 'Anyone with the link'."}
                    {activeImport === "sql" && "Compatible with SQLAlchemy drivers. Use sqlite:///filepath, postgresql://, or mysql://"}
                    {activeImport === "data-gov-in" && "Extracts datasets from the Open Government Data (OGD) Platform India."}
                  </p>
                </motion.div>
              )}

              {/* MCP Connect Dashboard */}
              {activeImport === "mcp" && (
                <motion.div
                  className="glass-card mt-4 p-6"
                  style={{ borderLeft: "3px solid #a855f7", boxShadow: "0 0 20px rgba(168,85,247,0.1)" }}
                  initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                >
                  {/* Status header */}
                  <div className="flex items-center justify-between mb-4 border-b border-[var(--glass-border)] pb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-[#a855f7]15 flex items-center justify-center text-[#a855f7]">
                        <Plug size={16} />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-[var(--text-primary)]">Model Context Protocol Connector</h4>
                        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                          {mcpIsConnected ? (
                            <span className="text-emerald-500 font-semibold flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                              Connected to {mcpServerInfo.name || "MCP Server"} v{mcpServerInfo.version || "1.0.0"}
                            </span>
                          ) : (
                            "Bridge DataSoul directly into the AI tool calling ecosystem"
                          )}
                        </p>
                      </div>
                    </div>
                    <button 
                      onClick={() => { handleMCPDisconnect(); setActiveImport(null); }} 
                      className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                    >
                      <X size={18} />
                    </button>
                  </div>

                  {!mcpIsConnected ? (
                    /* STEP 1: CONNECT SCREEN */
                    <div className="space-y-6">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Transport Connection Form */}
                        <div className="space-y-4">
                          <div>
                            <label className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider block mb-1">
                              Transport Protocol
                            </label>
                            <div className="flex gap-2">
                              <button 
                                onClick={() => setMcpTransport("stdio")}
                                className={`flex-1 py-2 text-xs font-semibold rounded-lg border transition-all ${mcpTransport === "stdio" ? "border-[#a855f7] bg-[#a855f7]10 text-[#a855f7]" : "border-[var(--glass-border)] hover:bg-[var(--glass-hover)]"}`}
                              >
                                Stdio (Local Command)
                              </button>
                              <button 
                                onClick={() => setMcpTransport("sse")}
                                className={`flex-1 py-2 text-xs font-semibold rounded-lg border transition-all ${mcpTransport === "sse" ? "border-[#a855f7] bg-[#a855f7]10 text-[#a855f7]" : "border-[var(--glass-border)] hover:bg-[var(--glass-hover)]"}`}
                              >
                                SSE (HTTP Stream)
                              </button>
                            </div>
                          </div>

                          {mcpTransport === "stdio" ? (
                            <div className="space-y-2">
                              <div>
                                <label className="text-xs font-medium text-[var(--text-secondary)] block mb-1">Executable Command</label>
                                <input 
                                  type="text" 
                                  value={mcpCommand} 
                                  onChange={(e) => setMcpCommand(e.target.value)}
                                  placeholder="e.g. npx, python, uvx"
                                  className="text-sm w-full px-4 py-2 rounded-lg bg-[var(--glass-bg)] border border-[var(--glass-border)] text-[var(--text-primary)] outline-none focus:border-[#a855f7]"
                                />
                              </div>
                              <div>
                                <label className="text-xs font-medium text-[var(--text-secondary)] block mb-1">Arguments</label>
                                <textarea 
                                  value={mcpArgsInput} 
                                  onChange={(e) => setMcpArgsInput(e.target.value)}
                                  placeholder="e.g. -y @modelcontextprotocol/server-sqlite --db ./mydb.sqlite"
                                  rows={3}
                                  className="text-sm w-full px-4 py-2 rounded-lg bg-[var(--glass-bg)] border border-[var(--glass-border)] text-[var(--text-primary)] outline-none focus:border-[#a855f7] font-mono"
                                />
                              </div>
                            </div>
                          ) : (
                            <div>
                              <label className="text-xs font-medium text-[var(--text-secondary)] block mb-1">Server SSE URL</label>
                              <input 
                                type="text" 
                                value={mcpSseUrl} 
                                onChange={(e) => setMcpSseUrl(e.target.value)}
                                placeholder="http://localhost:3001/sse"
                                className="text-sm w-full px-4 py-2 rounded-lg bg-[var(--glass-bg)] border border-[var(--glass-border)] text-[var(--text-primary)] outline-none focus:border-[#a855f7] font-mono"
                              />
                            </div>
                          )}

                          <button 
                            onClick={handleMCPConnect} 
                            disabled={mcpConnecting}
                            className="w-full flex items-center justify-center gap-2 bg-[#a855f7] hover:bg-[#9333ea] text-white py-2.5 rounded-lg text-sm font-semibold shadow transition-colors disabled:opacity-50"
                          >
                            {mcpConnecting ? (
                              <>
                                <Loader2 size={16} className="animate-spin" />
                                Connecting & Handshaking...
                              </>
                            ) : (
                              <>
                                <Plug size={16} />
                                Connect to MCP Server
                              </>
                            )}
                          </button>
                        </div>

                        {/* Awesome Catalog Directory */}
                        <div className="border border-[var(--glass-border)] rounded-xl bg-[var(--bg-secondary)] p-4 flex flex-col h-[280px]">
                          <div className="flex items-center gap-2 mb-2">
                            <Sparkles size={14} className="text-[#a855f7]" />
                            <h5 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">Awesome MCP Servers</h5>
                          </div>
                          
                          {/* Search & filters */}
                          <div className="relative mb-2">
                            <Search size={14} className="absolute left-3 top-2.5 text-[var(--text-muted)]" />
                            <input 
                              type="text"
                              value={mcpSearch}
                              onChange={(e) => setMcpSearch(e.target.value)}
                              placeholder="Search database connectors..."
                              className="text-xs w-full pl-8 pr-3 py-1.5 rounded-md bg-white border border-[var(--bg-border)] outline-none focus:border-[#a855f7]"
                            />
                          </div>

                          {/* Category chips scrollable */}
                          <div className="flex gap-1 overflow-x-auto pb-1 mb-2 max-w-full">
                            {categories.slice(0, 4).map(cat => (
                              <button
                                key={cat}
                                onClick={() => setMcpCategory(cat)}
                                className={`text-[9px] px-2 py-0.5 rounded-full font-medium whitespace-nowrap border transition-all ${mcpCategory === cat ? "border-[#a855f7] bg-[#a855f7]10 text-[#a855f7]" : "bg-white border-[var(--bg-border)] text-[var(--text-secondary)] hover:bg-gray-50"}`}
                              >
                                {cat.split(" ")[0]}
                              </button>
                            ))}
                          </div>

                          {/* Matching list */}
                          <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
                            {filteredServers.length > 0 ? (
                              filteredServers.map((srv) => (
                                <div key={srv.name} className="bg-white border border-[var(--bg-border)] rounded-lg p-2.5 hover:shadow-sm transition-all flex flex-col justify-between">
                                  <div>
                                    <div className="flex items-center justify-between">
                                      <span className="font-semibold text-xs text-[var(--text-primary)]">{srv.name}</span>
                                      <span className="text-[8px] px-1.5 py-0.5 rounded bg-purple-50 text-[#a855f7] border border-purple-100 font-medium">
                                        {srv.category.split(" ")[0]}
                                      </span>
                                    </div>
                                    <p className="text-[10px] text-[var(--text-secondary)] mt-0.5 line-clamp-2">{srv.description}</p>
                                  </div>
                                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-50">
                                    <span className="text-[8px] text-[var(--text-muted)] font-mono">{srv.repo}</span>
                                    <button 
                                      onClick={() => prefillServerTemplate(srv)}
                                      className="text-[9px] text-[#a855f7] hover:underline font-semibold flex items-center gap-0.5"
                                    >
                                      Pre-fill Config <ChevronRight size={10} />
                                    </button>
                                  </div>
                                </div>
                              ))
                            ) : (
                              <div className="text-center py-8 text-[var(--text-muted)] text-xs">No matching templates found</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    /* STEP 2: CONNECTED EXPLORER */
                    <div className="space-y-4">
                      {/* Discovery layout */}
                      <div className="grid grid-cols-3 gap-4 border border-[var(--glass-border)] rounded-xl overflow-hidden bg-white">
                        {/* LEFT COLUMN: Sidebar lists */}
                        <div className="col-span-1 border-r border-[var(--glass-border)] bg-[var(--bg-secondary)] flex flex-col h-[320px]">
                          {/* Tabs */}
                          <div className="flex border-b border-[var(--glass-border)] bg-gray-50 text-xs">
                            <button 
                              onClick={() => { setMcpActiveTab("tools"); setMcpSelectedTool(null); setMcpSelectedResource(null); setMcpExecutionResult(null); }}
                              className={`flex-1 py-2 font-semibold text-center transition-colors border-b-2 ${mcpActiveTab === "tools" ? "border-[#a855f7] text-[#a855f7] bg-white" : "border-transparent text-[var(--text-secondary)] hover:bg-gray-100"}`}
                            >
                              Tools ({mcpTools.length})
                            </button>
                            <button 
                              onClick={() => { setMcpActiveTab("resources"); setMcpSelectedTool(null); setMcpSelectedResource(null); setMcpExecutionResult(null); }}
                              className={`flex-1 py-2 font-semibold text-center transition-colors border-b-2 ${mcpActiveTab === "resources" ? "border-[#a855f7] text-[#a855f7] bg-white" : "border-transparent text-[var(--text-secondary)] hover:bg-gray-100"}`}
                            >
                              Resources ({mcpResources.length})
                            </button>
                          </div>

                          {/* List items */}
                          <div className="flex-1 overflow-y-auto p-2 space-y-1">
                            {mcpActiveTab === "tools" ? (
                              mcpTools.length > 0 ? (
                                mcpTools.map(t => (
                                  <button
                                    key={t.name}
                                    onClick={() => { setMcpSelectedTool(t); setMcpToolArguments({}); setMcpSelectedResource(null); setMcpExecutionResult(null); setMcpDataPreview(null); }}
                                    className={`w-full text-left p-2 rounded-lg text-xs transition-colors flex items-start gap-2 ${mcpSelectedTool?.name === t.name ? "bg-purple-50 border border-purple-100 text-[#a855f7]" : "hover:bg-[var(--glass-hover)] border border-transparent text-[var(--text-primary)]"}`}
                                  >
                                    <Cpu size={14} className="mt-0.5 flex-shrink-0" />
                                    <div className="truncate">
                                      <p className="font-semibold truncate">{t.name}</p>
                                      <p className="text-[10px] text-[var(--text-muted)] truncate">{t.description}</p>
                                    </div>
                                  </button>
                                ))
                              ) : (
                                <div className="text-center py-12 text-[var(--text-muted)] text-xs">No tools exposed</div>
                              )
                            ) : (
                              mcpResources.length > 0 ? (
                                mcpResources.map(r => (
                                  <button
                                    key={r.uri}
                                    onClick={() => { setMcpSelectedResource(r); setMcpSelectedTool(null); setMcpExecutionResult(null); setMcpDataPreview(null); }}
                                    className={`w-full text-left p-2 rounded-lg text-xs transition-colors flex items-start gap-2 ${mcpSelectedResource?.uri === r.uri ? "bg-purple-50 border border-purple-100 text-[#a855f7]" : "hover:bg-[var(--glass-hover)] border border-transparent text-[var(--text-primary)]"}`}
                                  >
                                    <Layers size={14} className="mt-0.5 flex-shrink-0" />
                                    <div className="truncate">
                                      <p className="font-semibold truncate">{r.name}</p>
                                      <p className="text-[10px] text-[var(--text-muted)] truncate">{r.uri}</p>
                                    </div>
                                  </button>
                                ))
                              ) : (
                                <div className="text-center py-12 text-[var(--text-muted)] text-xs">No resources exposed</div>
                              )
                            )}
                          </div>

                          {/* Control panel footer */}
                          <div className="p-2 border-t border-[var(--glass-border)] bg-gray-50 flex items-center justify-between text-xs">
                            <button 
                              onClick={() => mcpConnectionId && refreshMCPDetails(mcpConnectionId)}
                              className="text-[var(--text-secondary)] hover:text-[#a855f7] flex items-center gap-1 transition-colors"
                            >
                              <RefreshCw size={12} /> Refresh
                            </button>
                            <button 
                              onClick={handleMCPDisconnect}
                              className="text-red-500 hover:text-red-700 font-semibold"
                            >
                              Disconnect
                            </button>
                          </div>
                        </div>

                        {/* RIGHT AREA: Workspace Executer */}
                        <div className="col-span-2 flex flex-col h-[320px] overflow-y-auto p-4 bg-white">
                          {/* If nothing selected */}
                          {!mcpSelectedTool && !mcpSelectedResource && (
                            <div className="flex-1 flex flex-col items-center justify-center text-center text-[var(--text-muted)] py-12">
                              <Cpu size={32} className="text-gray-300 mb-2" />
                              <h5 className="font-semibold text-xs">Select a tool or resource to execute</h5>
                              <p className="text-[10px] mt-1 max-w-[240px]">Browse exposed capabilities from the sidebar tabs to begin loading data.</p>
                            </div>
                          )}

                          {/* Active Tool Form */}
                          {mcpSelectedTool && (
                            <div className="space-y-4 flex-1 flex flex-col justify-between">
                              <div>
                                <div className="flex items-center gap-1.5">
                                  <span className="text-[10px] font-bold uppercase tracking-wider bg-purple-50 text-[#a855f7] px-2 py-0.5 rounded border border-purple-100">
                                    Tool
                                  </span>
                                  <h4 className="font-bold text-sm text-[var(--text-primary)]">{mcpSelectedTool.name}</h4>
                                </div>
                                <p className="text-[11px] text-[var(--text-secondary)] mt-1">{mcpSelectedTool.description}</p>
                                
                                {/* Dynamic inputs generator */}
                                {mcpSelectedTool.inputSchema?.properties && (
                                  <div className="mt-3 space-y-2 border-t border-gray-100 pt-3">
                                    <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">Arguments</p>
                                    <div className="grid grid-cols-2 gap-2">
                                      {Object.entries(mcpSelectedTool.inputSchema.properties).map(([key, schema]: [string, any]) => {
                                        const isRequired = mcpSelectedTool.inputSchema.required?.includes(key);
                                        return (
                                          <div key={key} className="flex flex-col gap-0.5">
                                            <label className="text-[10px] font-medium text-[var(--text-primary)]">
                                              {key} {isRequired && <span className="text-red-500">*</span>}
                                            </label>
                                            
                                            {schema.type === "boolean" ? (
                                              <input
                                                type="checkbox"
                                                checked={!!mcpToolArguments[key]}
                                                onChange={(e) => setMcpToolArguments({ ...mcpToolArguments, [key]: e.target.checked })}
                                                className="w-4 h-4 accent-[#a855f7] mt-1"
                                              />
                                            ) : (
                                              <input
                                                type={schema.type === "number" || schema.type === "integer" ? "number" : "text"}
                                                value={mcpToolArguments[key] !== undefined ? mcpToolArguments[key] : ""}
                                                onChange={(e) => {
                                                  const val = schema.type === "number" || schema.type === "integer" 
                                                    ? (e.target.value === "" ? "" : Number(e.target.value))
                                                    : e.target.value;
                                                  setMcpToolArguments({ ...mcpToolArguments, [key]: val });
                                                }}
                                                placeholder={schema.description || `Enter ${schema.type || "string"} value`}
                                                className="text-xs px-2.5 py-1.5 rounded bg-[var(--bg-secondary)] border border-[var(--bg-border)] outline-none focus:border-[#a855f7]"
                                              />
                                            )}
                                            {schema.description && (
                                              <span className="text-[9px] text-[var(--text-muted)] line-clamp-1">{schema.description}</span>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  </div>
                                )}
                              </div>

                              <button 
                                onClick={handleMCPExecuteTool}
                                disabled={mcpExecuting}
                                className="w-full flex items-center justify-center gap-1.5 bg-[#a855f7] hover:bg-[#9333ea] text-white py-2 rounded-lg text-xs font-semibold shadow transition-colors disabled:opacity-50 mt-4"
                              >
                                {mcpExecuting ? (
                                  <>
                                    <Loader2 size={12} className="animate-spin" /> Running...
                                  </>
                                ) : (
                                  <>
                                    <Play size={12} /> Run Tool
                                  </>
                                )}
                              </button>
                            </div>
                          )}

                          {/* Active Resource Form */}
                          {mcpSelectedResource && (
                            <div className="space-y-4 flex-1 flex flex-col justify-between">
                              <div>
                                <div className="flex items-center gap-1.5">
                                  <span className="text-[10px] font-bold uppercase tracking-wider bg-purple-50 text-[#a855f7] px-2 py-0.5 rounded border border-purple-100">
                                    Resource
                                  </span>
                                  <h4 className="font-bold text-sm text-[var(--text-primary)]">{mcpSelectedResource.name}</h4>
                                </div>
                                <div className="mt-2 text-xs font-mono bg-gray-50 border border-gray-100 rounded-md p-1.5 truncate text-[10px]">
                                  {mcpSelectedResource.uri}
                                </div>
                                <p className="text-[11px] text-[var(--text-secondary)] mt-1.5">{mcpSelectedResource.description}</p>
                                {mcpSelectedResource.mimeType && (
                                  <p className="text-[10px] text-[var(--text-muted)] mt-1">Mime Type: <span className="font-mono">{mcpSelectedResource.mimeType}</span></p>
                                )}
                              </div>

                              <button 
                                onClick={() => handleMCPReadResource(mcpSelectedResource.uri, mcpSelectedResource.name)}
                                disabled={mcpExecuting}
                                className="w-full flex items-center justify-center gap-1.5 bg-[#a855f7] hover:bg-[#9333ea] text-white py-2 rounded-lg text-xs font-semibold shadow transition-colors disabled:opacity-50 mt-4"
                              >
                                {mcpExecuting ? (
                                  <>
                                    <Loader2 size={12} className="animate-spin" /> Reading...
                                  </>
                                ) : (
                                  <>
                                    <Eye size={12} /> Read Resource Content
                                  </>
                                )}
                              </button>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Diagnostic Log Console Toggle */}
                      <div className="border border-[var(--glass-border)] rounded-xl bg-gray-900 text-gray-200 overflow-hidden">
                        <button 
                          onClick={() => setMcpShowLogs(!mcpShowLogs)}
                          className="w-full px-4 py-2 flex items-center justify-between text-xs font-semibold text-gray-400 bg-gray-950 transition-colors hover:text-white"
                        >
                          <span className="flex items-center gap-1.5"><Terminal size={12} /> Connection Terminal Output</span>
                          <span>{mcpShowLogs ? "Hide" : "Show"}</span>
                        </button>
                        
                        {mcpShowLogs && (
                          <div className="p-3 font-mono text-[10px] max-h-[120px] overflow-y-auto space-y-1 bg-gray-900 border-t border-gray-950 select-text">
                            {mcpLogs.length > 0 ? (
                              mcpLogs.map((log, idx) => (
                                <div key={idx} className="whitespace-pre-wrap leading-relaxed">{log}</div>
                              ))
                            ) : (
                              <div className="text-gray-500 italic">No output received.</div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Tool/Resource Execution Results Panel */}
                      {mcpExecuting && (
                        <div className="glass-card flex items-center justify-center gap-2 py-8" style={{ borderStyle: "dashed" }}>
                          <Loader2 size={20} className="animate-spin text-[#a855f7]" />
                          <span className="text-xs text-[var(--text-secondary)]">Awaiting JSON-RPC response from server...</span>
                        </div>
                      )}

                      {mcpExecutionError && (
                        <div className="glass-card flex items-start gap-2.5" style={{ background: "rgba(239,68,68,0.06)", borderColor: "rgba(239,68,68,0.15)" }}>
                          <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
                          <div>
                            <p className="text-xs font-semibold text-red-600">Server Execution Failed</p>
                            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">{mcpExecutionError}</p>
                          </div>
                        </div>
                      )}

                      {mcpExecutionResult && !mcpExecuting && (
                        <div className="space-y-4">
                          {/* Data Preview block */}
                          {mcpDataPreview ? (
                            <div className="glass-card p-4 space-y-3" style={{ border: "1px solid rgba(168,85,247,0.2)" }}>
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-bold text-emerald-500 flex items-center gap-1">
                                  <CheckCircle2 size={14} /> Tabular Dataset Decoded!
                                </span>
                                <button 
                                  onClick={() => handleMCPImportData(mcpSelectedTool ? mcpSelectedTool.name : mcpSelectedResource.name)}
                                  disabled={mcpIsImporting}
                                  className="bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold px-4 py-1.5 rounded-lg shadow flex items-center gap-1.5 transition-colors disabled:opacity-50"
                                >
                                  {mcpIsImporting ? <Loader2 size={12} className="animate-spin" /> : <Database size={12} />}
                                  Load Dataset into DataSoul
                                </button>
                              </div>
                              
                              {mcpPreviewStatus && (
                                <p className="text-[10px] text-[var(--text-secondary)] italic">{mcpPreviewStatus}</p>
                              )}
                              
                              {/* Preview Table */}
                              <div className="border border-[var(--bg-border)] rounded-lg overflow-x-auto bg-[var(--bg-secondary)]">
                                <table className="w-full text-left text-[10px] border-collapse">
                                  <thead>
                                    <tr className="bg-gray-100 border-b border-[var(--bg-border)] font-semibold text-[var(--text-secondary)]">
                                      {mcpPreviewHeaders.slice(0, 8).map(hdr => (
                                        <th key={hdr} className="p-2 truncate font-mono border-r border-[var(--bg-border)] last:border-0">{hdr}</th>
                                      ))}
                                      {mcpPreviewHeaders.length > 8 && <th className="p-2 text-[var(--text-muted)]">+{mcpPreviewHeaders.length - 8} more</th>}
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {mcpDataPreview.map((row, rIdx) => (
                                      <tr key={rIdx} className="border-b border-[var(--bg-border)] last:border-0 bg-white hover:bg-gray-50">
                                        {mcpPreviewHeaders.slice(0, 8).map(hdr => (
                                          <td key={hdr} className="p-2 truncate border-r border-[var(--bg-border)] last:border-0">{String(row[hdr] !== undefined ? row[hdr] : "")}</td>
                                        ))}
                                        {mcpPreviewHeaders.length > 8 && <td className="p-2"></td>}
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          ) : (
                            <div className="glass-card flex items-start gap-2.5 p-4" style={{ background: "var(--bg-secondary)" }}>
                              <AlertCircle size={16} className="text-amber-500 mt-0.5 flex-shrink-0" />
                              <div className="flex-1">
                                <p className="text-xs font-semibold text-[var(--text-primary)]">Response Captured (Non-Tabular)</p>
                                <p className="text-[10px] text-[var(--text-muted)] mt-0.5">The result could not be parsed into rows. Review the raw output details below.</p>
                              </div>
                            </div>
                          )}

                          {/* Raw Output Block */}
                          <div className="border border-[var(--glass-border)] rounded-xl overflow-hidden text-xs">
                            <div className="px-4 py-2 bg-gray-50 font-semibold border-b border-[var(--glass-border)] text-[var(--text-secondary)] flex items-center gap-1">
                              <Code size={12} /> Raw JSON-RPC Response Content
                            </div>
                            <pre className="p-4 bg-gray-950 text-[#38bdf8] font-mono text-[10px] max-h-[200px] overflow-y-auto select-text leading-relaxed">
                              {JSON.stringify(mcpExecutionResult, null, 2)}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
          </>
        )}

        {/* ─── Upload Progress ─── */}
        <AnimatePresence>
          {file && (
            <motion.div
              className="glass-card mt-8"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <div className="flex items-center gap-4 mb-6">
                <div className="w-14 h-14 rounded-xl flex items-center justify-center" style={{ background: "var(--primary-glow)" }}>
                  <FileSpreadsheet size={28} className="text-[var(--primary)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold truncate">{uploadResult?.filename || file.name}</h3>
                  <p className="text-sm text-[var(--text-secondary)]">
                    {uploadResult
                      ? `${uploadResult.rows.toLocaleString()} rows × ${uploadResult.cols} columns • ${uploadResult.size_mb} MB`
                      : `${(file.size / 1024).toFixed(1)} KB`
                    }
                  </p>
                </div>
                {uploadComplete && (
                  <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring" }}>
                    <CheckCircle2 size={28} className="text-[var(--success)]" />
                  </motion.div>
                )}
              </div>

              {/* Progress bar */}
              <div className="h-2 rounded-full overflow-hidden mb-3" style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: uploadComplete ? "var(--success)" : "var(--gradient-primary)" }}
                  initial={{ width: 0 }}
                  animate={{ width: `${uploadProgress}%` }}
                  transition={{ ease: "easeOut", duration: 0.5 }}
                />
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--text-secondary)]">
                  {uploadComplete ? (
                    <span className="text-[var(--success)] font-medium flex items-center gap-1">
                      <CheckCircle2 size={14} /> Upload complete — redirecting to health report...
                    </span>
                  ) : isUploading ? (
                    <span className="flex items-center gap-2">
                      <Loader2 size={14} className="animate-spin" />
                      {uploadStep === 1 ? "Uploading to DataSoul..." : "Preparing dataset..."}
                    </span>
                  ) : "Ready"}
                </span>
                <span className="text-sm font-medium" style={{ color: uploadComplete ? "var(--success)" : "var(--primary)" }}>
                  {Math.round(uploadProgress)}%
                </span>
              </div>

              {/* Processing steps */}
              {(isUploading || uploadComplete) && (
                <motion.div className="mt-6 space-y-2" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
                  {[
                    { label: "Uploading file to DataSoul engine", done: uploadStep >= 2 },
                    { label: "Parsing file structure & detecting column types", done: uploadStep >= 2 },
                    { label: "Calculating statistics & quality metrics", done: uploadStep >= 3 },
                    { label: "Ready for profiling & threat detection", done: uploadStep >= 3 },
                  ].map((step, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      {step.done ? (
                        <CheckCircle2 size={14} className="text-[var(--success)]" />
                      ) : uploadStep > 0 ? (
                        <Loader2 size={14} className="text-[var(--primary)] animate-spin" />
                      ) : (
                        <div className="w-3.5 h-3.5 rounded-full border" style={{ borderColor: "var(--glass-border)" }} />
                      )}
                      <span style={{ color: step.done ? "var(--success)" : "var(--text-muted)" }}>
                        {step.label}
                      </span>
                    </div>
                  ))}
                </motion.div>
              )}

              {/* Show columns after upload */}
              {uploadResult && uploadComplete && (
                <motion.div className="mt-6 pt-4" style={{ borderTop: "1px solid var(--glass-border)" }} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <p className="text-xs text-[var(--text-muted)] mb-2">Detected Columns:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {uploadResult.columns.map((col, i) => (
                      <span key={i} className="text-xs px-2 py-1 rounded-md font-mono" style={{ background: "var(--glass-bg)", color: "var(--text-secondary)" }}>
                        {col}
                      </span>
                    ))}
                  </div>
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default function UploadPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 size={32} className="animate-spin text-[var(--primary)]" /></div>}>
      <UploadPageContent />
    </Suspense>
  );
}
