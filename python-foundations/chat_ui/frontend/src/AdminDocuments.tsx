
import { useEffect, useState } from "react";

interface Document {
  id: number;
  filename: string;
  size: number;
  pages: number;
  chunks: number;
  status: "indexing" | "indexed" | "failed";
  error: string | null;
  uploaded_at: string | null;
}

interface AdminDocumentsProps {
  token: string;
}

const API_URL = "http://127.0.0.1:8000";

export default function AdminDocuments({
  token,
}: AdminDocumentsProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(
    null
  );

  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(
    null
  );

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // -------------------------
  // Helpers
  // -------------------------

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";

    const units = ["Bytes", "KB", "MB", "GB"];
    const index = Math.floor(
      Math.log(bytes) / Math.log(1024)
    );

    const size = bytes / Math.pow(1024, index);

    return `${size.toFixed(index === 0 ? 0 : 2)} ${
      units[index]
    }`;
  };

  const formatDate = (
    dateString: string | null
  ): string => {
    if (!dateString) return "Unknown date";

    const date = new Date(dateString);

    if (Number.isNaN(date.getTime())) {
      return "Unknown date";
    }

    return date.toLocaleString();
  };

  const getErrorMessage = async (
    response: Response
  ): Promise<string> => {
    try {
      const data = await response.json();

      if (typeof data.detail === "string") {
        return data.detail;
      }

      return "An unexpected error occurred.";
    } catch {
      return "An unexpected error occurred.";
    }
  };

  // -------------------------
  // Fetch documents
  // -------------------------

  const fetchDocuments = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/api/documents`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          await getErrorMessage(response)
        );
      }

      const data = await response.json();

      // Backend returns:
      // { documents: [...] }
      //
      // Also accept a raw array for compatibility.

      const documentList: Document[] = Array.isArray(
        data
      )
        ? data
        : Array.isArray(data.documents)
        ? data.documents
        : [];

      setDocuments(documentList);
    } catch (err) {
      setDocuments([]);

      setError(
        err instanceof Error
          ? err.message
          : "Failed to load documents."
      );
    } finally {
      setLoading(false);
    }
  };

  // Fetch documents when component mounts
  // or when the authentication token changes.

  useEffect(() => {
    fetchDocuments();
  }, [token]);

  // -------------------------
  // Upload document
  // -------------------------

  const handleUpload = async () => {
    if (!selectedFile) {
      setError("Please select a PDF file first.");
      return;
    }

    if (
      !selectedFile.name
        .toLowerCase()
        .endsWith(".pdf")
    ) {
      setError("Only PDF files are allowed.");
      return;
    }

    setUploading(true);
    setError("");
    setSuccess("");

    const formData = new FormData();

    formData.append("file", selectedFile);

    try {
      const response = await fetch(
        `${API_URL}/api/documents/upload`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error(
          await getErrorMessage(response)
        );
      }

      const data = await response.json();

      setSuccess(
        `${data.filename} uploaded and indexed successfully. ` +
          `${data.pages} pages, ${data.chunks} chunks.`
      );

      setSelectedFile(null);

      // Clear the file input after successful upload.
      const fileInput = document.getElementById(
        "document-file-input"
      ) as HTMLInputElement | null;

      if (fileInput) {
        fileInput.value = "";
      }

      await fetchDocuments();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to upload document."
      );

      // Refresh because the backend may have saved
      // the PDF and marked its indexing as failed.
      await fetchDocuments();
    } finally {
      setUploading(false);
    }
  };

  // -------------------------
  // Delete document
  // -------------------------

  const handleDelete = async (
    filename: string
  ) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${filename}"?\n\n` +
        "This will remove the document from the knowledge base."
    );

    if (!confirmed) return;

    setDeleting(filename);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        `${API_URL}/api/documents/${encodeURIComponent(
          filename
        )}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          await getErrorMessage(response)
        );
      }

      setSuccess(
        `${filename} deleted successfully.`
      );

      await fetchDocuments();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to delete document."
      );
    } finally {
      setDeleting(null);
    }
  };

  // -------------------------
  // Render
  // -------------------------

  return (
    <div className="admin-documents">
      <div className="admin-documents-header">
        <div>
          <h2>Manage Documents</h2>

          <p>
            Upload and manage documents in the
            organization's knowledge base.
          </p>
        </div>

        <button
          type="button"
          className="refresh-documents-button"
          onClick={fetchDocuments}
          disabled={loading || uploading}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {/* -------------------------
          Alerts
      ------------------------- */}

      {error && (
        <div
          className="admin-alert admin-alert-error"
          role="alert"
        >
          <span>{error}</span>

          <button
            type="button"
            onClick={() => setError("")}
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}

      {success && (
        <div
          className="admin-alert admin-alert-success"
          role="status"
        >
          <span>{success}</span>

          <button
            type="button"
            onClick={() => setSuccess("")}
            aria-label="Dismiss success message"
          >
            ×
          </button>
        </div>
      )}

      {/* -------------------------
          Upload section
      ------------------------- */}

      <div className="admin-upload-section">
        <h3>Upload a document</h3>

        <p>
          Select a PDF to add it to the knowledge
          base. The document will be validated and
          indexed automatically.
        </p>

        <div className="admin-upload-controls">
          <input
            id="document-file-input"
            type="file"
            accept=".pdf,application/pdf"
            disabled={uploading}
            onChange={(event) => {
              const file =
                event.target.files?.[0] ?? null;

              setSelectedFile(file);
              setError("");
              setSuccess("");
            }}
          />

          <button
            type="button"
            className="upload-document-button"
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
          >
            {uploading
              ? "Uploading and indexing..."
              : "Upload PDF"}
          </button>
        </div>

        {selectedFile && (
          <div className="selected-file-info">
            <span>
              Selected: {selectedFile.name}
            </span>

            <span>
              {formatFileSize(selectedFile.size)}
            </span>
          </div>
        )}

        {uploading && (
          <div className="upload-progress-message">
            <span className="admin-spinner" />

            <span>
              Validating PDF and indexing its
              contents. This may take a while for
              large documents.
            </span>
          </div>
        )}
      </div>

      {/* -------------------------
          Document list
      ------------------------- */}

      <div className="admin-document-list-section">
        <div className="admin-document-list-header">
          <h3>Knowledge Base Documents</h3>

          <span className="document-count">
            {documents.length}{" "}
            {documents.length === 1
              ? "document"
              : "documents"}
          </span>
        </div>

        {loading && documents.length === 0 ? (
          <div className="admin-empty-state">
            <span className="admin-spinner" />

            <p>Loading documents...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="admin-empty-state">
            <p>No documents found.</p>

            <span>
              Upload a PDF to start building your
              knowledge base.
            </span>
          </div>
        ) : (
          <div className="admin-document-list">
            {documents.map((document) => (
              <div
                key={document.id}
                className="admin-document-card"
              >
                <div className="admin-document-main">
                  <div className="admin-document-info">
                    <div className="admin-document-title">
                      <span className="document-pdf-icon">
                        PDF
                      </span>

                      <h4>
                        {document.filename}
                      </h4>
                    </div>

                    <div className="admin-document-meta">
                      <span>
                        {formatFileSize(
                          document.size
                        )}
                      </span>

                      <span>
                        {document.pages}{" "}
                        {document.pages === 1
                          ? "page"
                          : "pages"}
                      </span>

                      <span>
                        {document.chunks}{" "}
                        {document.chunks === 1
                          ? "chunk"
                          : "chunks"}
                      </span>
                    </div>

                    <div className="admin-document-date">
                      Uploaded{" "}
                      {formatDate(
                        document.uploaded_at
                      )}
                    </div>
                  </div>

                  <div className="admin-document-actions">
                    <span
                      className={`document-status ${document.status}`}
                    >
                      {document.status ===
                        "indexed" && (
                        <>
                          <span>✓</span>
                          Indexed
                        </>
                      )}

                      {document.status ===
                        "indexing" && (
                        <>
                          <span>⏳</span>
                          Indexing
                        </>
                      )}

                      {document.status ===
                        "failed" && (
                        <>
                          <span>✕</span>
                          Failed
                        </>
                      )}

                      {![
                        "indexed",
                        "indexing",
                        "failed",
                      ].includes(document.status) && (
                        <>Unknown status</>
                      )}
                    </span>

                    <button
                      type="button"
                      className="delete-document-button"
                      onClick={() =>
                        handleDelete(
                          document.filename
                        )
                      }
                      disabled={
                        deleting ===
                        document.filename
                      }
                    >
                      {deleting ===
                      document.filename
                        ? "Deleting..."
                        : "Delete"}
                    </button>
                  </div>
                </div>

                {document.status === "failed" &&
                  document.error && (
                    <div className="document-error">
                      <strong>
                        Indexing error:
                      </strong>

                      <p>{document.error}</p>
                    </div>
                  )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}