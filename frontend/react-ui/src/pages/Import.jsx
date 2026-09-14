import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Upload, FileText, FileImage, MessageCircle, Trash2,
  ChevronRight, CheckCircle2, AlertCircle, Loader2,
  ArrowRight, DownloadCloud, Edit2, X,
} from "lucide-react";
import { smartIngest, smartConfirm } from "../api";

// ── Constants ─────────────────────────────────────────────────────────────────
const ACCEPTED = ".txt,.pdf,.jpg,.jpeg,.png,.webp";
const TYPE_OPTS = ["invoice", "payable", "payment", "receipt"];
const CAT_OPTS  = ["general", "product", "service", "fixed", "utilities", "rent", "salary"];

const CONF_COLOR = { high: "var(--green)", medium: "var(--yellow)", low: "var(--red)", none: "var(--text-muted)" };
const CONF_LABEL = { high: "High", medium: "Medium", low: "Low", none: "Error" };

const SOURCE_ICON = { whatsapp: MessageCircle, pdf: FileText, image: FileImage };

function fileIcon(filename) {
  const ext = filename?.split(".").pop()?.toLowerCase();
  if (ext === "txt") return MessageCircle;
  if (ext === "pdf") return FileText;
  return FileImage;
}

function FileChip({ file, onRemove }) {
  const Icon = fileIcon(file.name);
  return (
    <div className="import-file-chip">
      <Icon size={13} />
      <span className="text-sm">{file.name}</span>
      <button className="import-file-chip__remove" onClick={onRemove} title="Remove">
        <X size={11} />
      </button>
    </div>
  );
}

// ── Step 1 — Upload ───────────────────────────────────────────────────────────
function StepUpload({ files, setFiles, onAnalyse, loading }) {
  const inputRef = useRef();
  const [dragging, setDragging] = useState(false);

  const addFiles = (incoming) => {
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name));
      return [...prev, ...Array.from(incoming).filter((f) => !existing.has(f.name))];
    });
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  }, []);

  return (
    <div className="import-step">
      <h2 className="import-step__title">Upload your documents</h2>
      <p className="import-step__desc text-muted">
        Drag &amp; drop WhatsApp chat exports (.txt), invoice PDFs, or receipt images.
        We'll extract financial details automatically.
      </p>

      {/* Supported types legend */}
      <div className="import-types-row">
        {[
          { icon: MessageCircle, label: "WhatsApp Chat", ext: ".txt",  color: "var(--green)" },
          { icon: FileText,      label: "Invoice / Bill", ext: ".pdf",  color: "var(--primary)" },
          { icon: FileImage,     label: "Receipt Image",  ext: ".jpg / .png", color: "var(--yellow)" },
        ].map(({ icon: Icon, label, ext, color }) => (
          <div key={label} className="import-type-card">
            <Icon size={20} style={{ color }} />
            <span className="import-type-card__label">{label}</span>
            <span className="import-type-card__ext text-muted text-sm">{ext}</span>
          </div>
        ))}
      </div>

      {/* Drop zone */}
      <div
        className={`import-dropzone${dragging ? " import-dropzone--active" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <DownloadCloud size={36} className="import-dropzone__icon" />
        <p className="import-dropzone__text">Drop files here or <span className="link-text">click to browse</span></p>
        <p className="text-muted text-sm">WhatsApp .txt · PDF · JPG · PNG</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED}
          style={{ display: "none" }}
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="import-file-list">
          {files.map((f, i) => (
            <FileChip
              key={f.name}
              file={f}
              onRemove={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
            />
          ))}
        </div>
      )}

      <button
        className="btn btn--primary import-analyse-btn"
        disabled={files.length === 0 || loading}
        onClick={onAnalyse}
      >
        {loading
          ? <><Loader2 size={15} className="spin" /> Analysing…</>
          : <><ArrowRight size={15} /> Analyse {files.length > 0 ? `${files.length} file${files.length > 1 ? "s" : ""}` : ""}</>}
      </button>
    </div>
  );
}

// ── Step 2 — Preview ──────────────────────────────────────────────────────────
function EditableCell({ value, onChange, type = "text", options }) {
  if (options) {
    return (
      <select className="import-cell-select" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  return (
    <input
      className="import-cell-input"
      type={type}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

function StepPreview({ rows, setRows, onConfirm, onBack, loading }) {
  const del = (id) => setRows((prev) => prev.filter((r) => r._id !== id));
  const upd = (id, field, val) =>
    setRows((prev) => prev.map((r) => r._id === id ? { ...r, [field]: val } : r));

  const withAmount = rows.filter((r) => r.amount && !r.error).length;

  return (
    <div className="import-step">
      <h2 className="import-step__title">Review extracted data</h2>
      <p className="import-step__desc text-muted">
        {rows.length} row{rows.length !== 1 ? "s" : ""} extracted — {withAmount} with amounts detected.
        Edit, change type, or delete before importing.
      </p>

      <div className="import-table-wrap">
        <table className="import-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Party / Sender</th>
              <th>Amount (₹)</th>
              <th>Date</th>
              <th>Type</th>
              <th>Category</th>
              <th>Confidence</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              if (row.error) {
                return (
                  <tr key={row._id} className="import-row import-row--error">
                    <td colSpan={7}>
                      <AlertCircle size={13} style={{ color: "var(--red)", marginRight: 6 }} />
                      <strong>{row.filename}</strong>: {row.error}
                    </td>
                    <td><button className="import-del-btn" onClick={() => del(row._id)}><Trash2 size={13} /></button></td>
                  </tr>
                );
              }
              const SrcIcon = SOURCE_ICON[row.source] ?? FileText;
              return (
                <tr key={row._id} className="import-row">
                  <td>
                    <span className="import-src-badge">
                      <SrcIcon size={12} />
                      {row.source}
                    </span>
                  </td>
                  <td>
                    <EditableCell value={row.party} onChange={(v) => upd(row._id, "party", v)} />
                  </td>
                  <td>
                    <EditableCell value={row.amount} type="number" onChange={(v) => upd(row._id, "amount", v)} />
                  </td>
                  <td>
                    <EditableCell value={row.date} type="date" onChange={(v) => upd(row._id, "date", v)} />
                  </td>
                  <td>
                    <EditableCell
                      value={row.suggested_type || row.type || "invoice"}
                      options={TYPE_OPTS}
                      onChange={(v) => upd(row._id, "suggested_type", v)}
                    />
                  </td>
                  <td>
                    <EditableCell
                      value={row.category || "general"}
                      options={CAT_OPTS}
                      onChange={(v) => upd(row._id, "category", v)}
                    />
                  </td>
                  <td>
                    <span
                      className="import-conf-badge"
                      style={{ color: CONF_COLOR[row.confidence] ?? "var(--text-muted)" }}
                    >
                      {CONF_LABEL[row.confidence] ?? row.confidence}
                    </span>
                  </td>
                  <td>
                    <button className="import-del-btn" onClick={() => del(row._id)} title="Remove row">
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {rows.length === 0 && (
          <div className="import-empty">No rows — all removed.</div>
        )}
      </div>

      <div className="import-step__actions">
        <button className="btn btn--ghost" onClick={onBack}>← Back</button>
        <button
          className="btn btn--primary"
          disabled={rows.filter((r) => !r.error).length === 0 || loading}
          onClick={onConfirm}
        >
          {loading
            ? <><Loader2 size={15} className="spin" /> Importing…</>
            : <><CheckCircle2 size={15} /> Confirm &amp; Import {rows.filter((r) => !r.error && r.amount > 0).length} row{rows.filter((r) => !r.error && r.amount > 0).length !== 1 ? "s" : ""}</>}
        </button>
      </div>
    </div>
  );
}

// ── Step 3 — Done ─────────────────────────────────────────────────────────────
function StepDone({ counts, onReset }) {
  const navigate = useNavigate();
  return (
    <div className="import-step import-step--done">
      <CheckCircle2 size={52} className="import-done-icon" />
      <h2 className="import-step__title">Import complete!</h2>

      <div className="import-done-counts">
        <div className="import-done-stat">
          <span className="import-done-stat__num">{counts.invoice ?? 0}</span>
          <span className="text-muted text-sm">Invoices / Receipts</span>
        </div>
        <div className="import-done-stat">
          <span className="import-done-stat__num">{counts.payable ?? 0}</span>
          <span className="text-muted text-sm">Payables</span>
        </div>
        <div className="import-done-stat">
          <span className="import-done-stat__num">{counts.skipped ?? 0}</span>
          <span className="text-muted text-sm">Skipped</span>
        </div>
      </div>

      <div className="import-done-actions">
        <button className="btn btn--primary" onClick={() => navigate("/receivables")}>
          View Receivables <ChevronRight size={14} />
        </button>
        <button className="btn btn--secondary" onClick={() => navigate("/payables")}>
          View Payables <ChevronRight size={14} />
        </button>
        <button className="btn btn--ghost" onClick={onReset}>
          Import More
        </button>
      </div>
    </div>
  );
}

// ── Stepper indicator ─────────────────────────────────────────────────────────
function Stepper({ step }) {
  const steps = ["Upload", "Review", "Done"];
  return (
    <div className="import-stepper">
      {steps.map((label, i) => (
        <div key={label} className={`import-stepper__item${i < step ? " done" : i === step ? " active" : ""}`}>
          <div className="import-stepper__dot">{i < step ? <CheckCircle2 size={14} /> : i + 1}</div>
          <span className="import-stepper__label">{label}</span>
          {i < steps.length - 1 && <div className="import-stepper__line" />}
        </div>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ImportPage() {
  const [step,    setStep]    = useState(0);
  const [files,   setFiles]   = useState([]);
  const [rows,    setRows]    = useState([]);
  const [counts,  setCounts]  = useState({});
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const handleAnalyse = async () => {
    setLoading(true);
    setError(null);
    try {
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f));
      const data = await smartIngest(fd);
      setRows(data.rows ?? []);
      setStep(1);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    setLoading(true);
    setError(null);
    try {
      const confirmRows = rows
        .filter((r) => !r.error && parseFloat(r.amount) > 0)
        .map((r) => ({
          party:    r.party,
          amount:   parseFloat(r.amount),
          date:     r.date,
          type:     r.suggested_type || r.type || "invoice",
          category: r.category || "general",
        }));
      const data = await smartConfirm(confirmRows);
      setCounts(data.counts ?? {});
      setStep(2);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setStep(0); setFiles([]); setRows([]); setCounts({}); setError(null);
  };

  return (
    <div className="page import-page">
      <div className="import-header">
        <h1 className="import-page-title">Smart Import</h1>
        <p className="text-muted">
          Automatically extract financial data from WhatsApp chats, invoices &amp; receipts.
        </p>
      </div>

      <Stepper step={step} />

      {error && (
        <div className="import-error-banner">
          <AlertCircle size={15} /> {error}
        </div>
      )}

      {step === 0 && (
        <StepUpload
          files={files}
          setFiles={setFiles}
          onAnalyse={handleAnalyse}
          loading={loading}
        />
      )}
      {step === 1 && (
        <StepPreview
          rows={rows}
          setRows={setRows}
          onConfirm={handleConfirm}
          onBack={() => setStep(0)}
          loading={loading}
        />
      )}
      {step === 2 && (
        <StepDone counts={counts} onReset={reset} />
      )}
    </div>
  );
}
