import { useState, useRef } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function UploadPage() {
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef();

  const addFiles = (newFiles) => {
    const mapped = Array.from(newFiles).map((f) => ({
      file: f,
      id: Math.random().toString(36).slice(2),
      status: "pending",
      progress: 0,
    }));
    setFiles((prev) => [...prev, ...mapped]);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  };

  const uploadAll = async () => {
    setUploading(true);
    for (const item of files.filter((f) => f.status === "pending")) {
      setFiles((prev) =>
        prev.map((f) => (f.id === item.id ? { ...f, status: "processing", progress: 30 } : f))
      );
      try {
        const formData = new FormData();
        formData.append("file", item.file);
        const res = await fetch(`${API}/api/invoices/upload`, {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (res.ok) {
          setFiles((prev) =>
            prev.map((f) =>
              f.id === item.id
                ? { ...f, status: "done", progress: 100, fileId: data.file_id }
                : f
            )
          );
        } else {
          throw new Error(data.detail || "Upload failed");
        }
      } catch (err) {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === item.id ? { ...f, status: "failed", error: err.message } : f
          )
        );
      }
    }
    setUploading(false);
  };

  const removeFile = (id) =>
    setFiles((prev) => prev.filter((f) => f.id !== id));

  const fileIcon = (name) => {
    const ext = name.split(".").pop().toLowerCase();
    return ext === "pdf" ? "📄" : "🖼️";
  };

  const hasPending = files.some((f) => f.status === "pending");

  return (
    <div className="upload-page">
      {/* Drop zone */}
      <div>
        <div
          className={`upload-zone ${dragging ? "dragging" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current.click()}
        >
          <div className="upload-icon">📁</div>
          <div className="upload-title">Drop invoices here</div>
          <div className="upload-sub">
            Supports PDF, JPG, PNG · Max 20MB per file
          </div>
          <button className="btn btn-primary" onClick={(e) => { e.stopPropagation(); inputRef.current.click(); }}>
            Browse Files
          </button>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            multiple
            style={{ display: "none" }}
            onChange={(e) => addFiles(e.target.files)}
          />
        </div>

        {hasPending && (
          <div style={{ marginTop: 16, display: "flex", gap: 12 }}>
            <button
              className="btn btn-primary"
              onClick={uploadAll}
              disabled={uploading}
            >
              {uploading ? (
                <><span className="spinner" /> Processing...</>
              ) : (
                <>⚡ Extract All</>
              )}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => setFiles([])}
              disabled={uploading}
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* File queue */}
      <div>
        <div className="section-title">
          📋 Queue
          {files.length > 0 && (
            <span style={{ color: "var(--muted)", fontWeight: 400, fontSize: 13 }}>
              {files.length} file{files.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        {files.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">🗂️</div>
            <div>No files added yet</div>
          </div>
        ) : (
          <div className="file-queue">
            {files.map((item) => (
              <div className="file-item" key={item.id}>
                <span className="file-icon">{fileIcon(item.file.name)}</span>
                <div className="file-info">
                  <div className="file-name">{item.file.name}</div>
                  <div className="file-size">
                    {(item.file.size / 1024).toFixed(1)} KB
                  </div>
                  {item.status === "processing" && (
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{ width: `${item.progress}%` }}
                      />
                    </div>
                  )}
                  {item.status === "failed" && (
                    <div style={{ color: "var(--red)", fontSize: 12, marginTop: 4 }}>
                      {item.error}
                    </div>
                  )}
                  {item.status === "done" && item.fileId && (
                    <div style={{ color: "var(--green)", fontSize: 12, fontFamily: "var(--mono)", marginTop: 4 }}>
                      ID: {item.fileId.slice(0, 8)}...
                    </div>
                  )}
                </div>
                <span className={`status-badge status-${item.status}`}>
                  {item.status}
                </span>
                {item.status !== "processing" && (
                  <button
                    onClick={() => removeFile(item.id)}
                    style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: 16 }}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
