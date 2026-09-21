import { useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8000";

interface DocumentItem {
  filename: string;
  size: number;
  uploaded_at: string;
}
interface AdminDocumentsProps {
  token: string;
}

function AdminDocuments({
  token,
}: AdminDocumentsProps) {
  const [documents, setDocuments] =
    useState<DocumentItem[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [uploading, setUploading] =
    useState(false);

  const [deleting, setDeleting] =
    useState<string | null>(null);

  const [error, setError] =
    useState("");

  const [success, setSuccess] =
    useState("");

  const [selectedFile, setSelectedFile] =
    useState<File | null>(null);


async function loadDocuments() {
  setLoading(true);
  setError("");

  try {
    const response = await fetch(
      `${API_URL}/api/documents`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!response.ok) {
      const data =
        await response.json();

      throw new Error(
        data.detail ||
          "Failed to load documents."
      );
    }

    const data =
      await response.json();

    setDocuments(
      Array.isArray(data)
        ? data
        : data.documents ?? []
    );
  } catch (error) {
    setError(
      error instanceof Error
        ? error.message
        : "Failed to load documents."
    );

    setDocuments([]);
  } finally {
    setLoading(false);
  }
}


  useEffect(() => {
    loadDocuments();
  }, [token]);


  function handleFileChange(
    event: React.ChangeEvent<HTMLInputElement>
  ) {
    const file =
      event.target.files?.[0];

    if (!file) {
      setSelectedFile(null);
      return;
    }

    if (
      !file.name
        .toLowerCase()
        .endsWith(".pdf")
    ) {
      setError(
        "Only PDF files are allowed."
      );

      setSelectedFile(null);
      return;
    }

    setError("");
    setSuccess("");
    setSelectedFile(file);
  }


  async function uploadDocument() {
    if (!selectedFile) {
      setError(
        "Please select a PDF file first."
      );

      return;
    }

    setUploading(true);
    setError("");
    setSuccess("");

    try {
      const formData =
        new FormData();

      formData.append(
        "file",
        selectedFile
      );

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
        const data =
          await response.json();

        throw new Error(
          data.detail ||
            "Document upload failed."
        );
      }

      const data =
        await response.json();

      setSuccess(
        data.message ||
          "Document uploaded successfully."
      );

      setSelectedFile(null);

      const input =
        document.getElementById(
          "document-file"
        ) as HTMLInputElement | null;

      if (input) {
        input.value = "";
      }

      await loadDocuments();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Document upload failed."
      );
    } finally {
      setUploading(false);
    }
  }


  async function deleteDocument(
    filename: string
  ) {
    const confirmed =
      window.confirm(
        `Delete "${filename}" from the knowledge base?`
      );

    if (!confirmed) {
      return;
    }

    setDeleting(filename);
    setError("");
    setSuccess("");

    try {
      const response =
        await fetch(
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
        const data =
          await response.json();

        throw new Error(
          data.detail ||
            "Failed to delete document."
        );
      }

      const data =
        await response.json();

      setSuccess(
        data.message ||
          "Document deleted successfully."
      );

      await loadDocuments();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Failed to delete document."
      );
    } finally {
      setDeleting(null);
    }
  }


  function formatFileSize(
    bytes: number
  ) {
    if (bytes < 1024) {
      return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
      return `${(
        bytes / 1024
      ).toFixed(1)} KB`;
    }

    return `${(
      bytes /
      (1024 * 1024)
    ).toFixed(1)} MB`;
  }


  return (
    <section className="admin-documents">

      <div className="admin-documents-header">

        <div>
          <div className="admin-eyebrow">
            ADMIN
          </div>

          <h2>
            Knowledge Base
          </h2>

          <p>
            Upload and manage the documents
            your AI assistant can use.
          </p>
        </div>

        <button
          className="refresh-documents-button"
          onClick={loadDocuments}
          disabled={loading}
        >
          ↻ Refresh
        </button>

      </div>


      <div className="document-upload-card">

        <div className="upload-heading">
          <div className="upload-icon">
            ↑
          </div>

          <div>
            <h3>
              Add a document
            </h3>

            <p>
              Upload a PDF to add it to
              the AI knowledge base.
            </p>
          </div>
        </div>


        <div className="upload-controls">

          <input
            id="document-file"
            type="file"
            accept=".pdf,application/pdf"
            onChange={
              handleFileChange
            }
          />

          <button
            className="upload-button"
            onClick={
              uploadDocument
            }
            disabled={
              uploading ||
              !selectedFile
            }
          >
            {uploading
              ? "Processing..."
              : "Upload PDF"}
          </button>

        </div>


        {selectedFile && (
          <div className="selected-file">
            Selected:
            <strong>
              {selectedFile.name}
            </strong>
          </div>
        )}

      </div>


      {error && (
        <div className="document-alert error">
          {error}
        </div>
      )}


      {success && (
        <div className="document-alert success">
          {success}
        </div>
      )}


      <div className="documents-list-card">

        <div className="documents-list-header">
          <h3>
            Uploaded documents
          </h3>

          <span>
            {documents.length}
          </span>
        </div>


        {loading ? (
          <div className="documents-empty">
            <div className="spinner"></div>
            <p>
              Loading documents...
            </p>
          </div>
        ) : documents.length === 0 ? (
          <div className="documents-empty">
            <div className="empty-document-icon">
              📄
            </div>

            <h4>
              No uploaded documents
            </h4>

            <p>
              Upload your first PDF above.
            </p>
          </div>
        ) : (
          <div className="document-list">

            {documents.map(
              (document) => (
                <div
                  className="document-row"
                  key={
                    document.filename
                  }
                >

                  <div className="document-main">

                    <div className="document-file-icon">
                      PDF
                    </div>

                    <div className="document-details">

                      <div className="document-name">
                        {
                          document.filename
                        }
                      </div>

                      <div className="document-meta">
                        {formatFileSize(
                          document.size
                        )}

                        {document.uploaded_at &&
                          ` • ${new Date(
                            document.uploaded_at
                          ).toLocaleDateString()}`}
                      </div>

                    </div>

                  </div>


                  <button
                    className="delete-document-button"
                    onClick={() =>
                      deleteDocument(
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
              )
            )}

          </div>
        )}

      </div>

    </section>
  );
}

export default AdminDocuments;

