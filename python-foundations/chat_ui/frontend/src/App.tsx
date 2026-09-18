import {
  useEffect,
  useRef,
  useState,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

function createSessionId() {
  return crypto.randomUUID();
}

interface Source {
  file: string | null;
  page: string | null;
  score: number | null;
}

interface ChatResponse {
  answer: string;
  sources: Source[];
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  timestamp: Date;
}

function App() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(
  createSessionId()
   );

  const messagesEndRef =
    useRef<HTMLDivElement | null>(null);

  const textareaRef =
    useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  useEffect(() => {
    const textarea = textareaRef.current;

    if (!textarea) {
      return;
    }

    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(
      textarea.scrollHeight,
      160
    )}px`;
  }, [message]);

  function startNewChat() {
    if (loading) {
      return;
    }

    setMessages([]);
    setMessage("");
    setSessionId(createSessionId());
  }

  async function sendMessage() {
    if (!message.trim() || loading) {
      return;
    }

    const currentMessage = message.trim();

    const userMessage: Message = {
      role: "user",
      content: currentMessage,
      timestamp: new Date(),
    };

    setMessages((previous) => [
      ...previous,
      userMessage,
    ]);

    setMessage("");
    setLoading(true);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/chat",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            session_id: sessionId,
            message: currentMessage,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          `Request failed: ${response.status}`
        );
      }

      const data: ChatResponse =
        await response.json();

      const assistantMessage: Message = {
        role: "assistant",
        content: data.answer,
        sources: data.sources,
        timestamp: new Date(),
      };

      setMessages((previous) => [
        ...previous,
        assistantMessage,
      ]);
    } catch (error) {
      console.error(error);

      const errorMessage: Message = {
        role: "assistant",
        content:
          "Sorry, something went wrong while contacting the backend. Please try again.",
        timestamp: new Date(),
      };

      setMessages((previous) => [
        ...previous,
        errorMessage,
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(
    event: React.KeyboardEvent<HTMLTextAreaElement>
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      sendMessage();
    }
  }

  function formatTime(date: Date) {
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="brand">
            <div className="brand-icon">
              AI
            </div>

            <div>
              <h1>RAG Assistant</h1>

              <p>
                Your document knowledge assistant
              </p>
            </div>
          </div>

          <button
            className="new-chat-button"
            onClick={startNewChat}
            disabled={
              loading || messages.length === 0
            }
          >
            <span>＋</span>
            New Chat
          </button>
        </div>
      </header>

      <main className="chat-container">
        <div className="messages">

          {messages.length === 0 && (
            <div className="welcome">
              <div className="welcome-icon">
                ✦
              </div>

              <h2>
                How can I help you?
              </h2>

              <p>
                Ask questions about the documents
                in your knowledge base.
              </p>

              <div className="suggestions">
                <button
                  onClick={() =>
                    setMessage(
                      "Who is Denzel Okoth?"
                    )
                  }
                >
                  Who is Denzel Okoth?
                </button>

                <button
                  onClick={() =>
                    setMessage(
                      "What information is available in the documents?"
                    )
                  }
                >
                  What information is available?
                </button>

                <button
                  onClick={() =>
                    setMessage(
                      "Summarize the main topics in the documents."
                    )
                  }
                >
                  Summarize the documents
                </button>
              </div>
            </div>
          )}

          {messages.map((msg, index) => (
            <div
              key={index}
              className={`message-row ${msg.role}`}
            >
              <div className="message">

                <div className="message-header">
                  <span className="message-label">
                    {msg.role === "user"
                      ? "You"
                      : "Assistant"}
                  </span>

                  <span className="message-time">
                    {formatTime(
                      msg.timestamp
                    )}
                  </span>
                </div>

                <div className="message-content">
                  {msg.role ===
                  "assistant" ? (
                    <ReactMarkdown
                      remarkPlugins={[
                        remarkGfm,
                      ]}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  ) : (
                    <p>{msg.content}</p>
                  )}
                </div>

                {msg.sources &&
                  msg.sources.length > 0 && (
                    <div className="sources">
                      <div className="sources-title">
                        <span>Sources</span>

                        <span className="sources-count">
                          {msg.sources.length}
                        </span>
                      </div>

                      <div className="source-list">
                        {msg.sources.map(
                          (
                            source,
                            sourceIndex
                          ) => (
                            <div
                              className="source-card"
                              key={sourceIndex}
                            >
                              <div className="source-icon">
                                📄
                              </div>

                              <div className="source-info">
                                <div className="source-file">
                                  {source.file ||
                                    "Unknown document"}
                                </div>

                                <div className="source-meta">
                                  <span>
                                    Page{" "}
                                    {source.page ||
                                      "—"}
                                  </span>

                                  {source.score !==
                                    null && (
                                    <span>
                                      Relevance{" "}
                                      {source.score.toFixed(
                                        3
                                      )}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          )
                        )}
                      </div>
                    </div>
                  )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message-row assistant">
              <div className="message">

                <div className="message-header">
                  <span className="message-label">
                    Assistant
                  </span>
                </div>

                <div className="typing">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>

              </div>
            </div>
          )}

          <div ref={messagesEndRef} />

        </div>

        <div className="input-wrapper">
          <div className="input-area">

            <textarea
              ref={textareaRef}
              value={message}
              onChange={(event) =>
                setMessage(
                  event.target.value
                )
              }
              onKeyDown={handleKeyDown}
              placeholder="Ask something..."
              rows={1}
              disabled={loading}
            />

            <button
              className="send-button"
              onClick={sendMessage}
              disabled={
                loading ||
                !message.trim()
              }
              aria-label="Send message"
            >
              {loading ? (
                <span className="spinner"></span>
              ) : (
                <span>↑</span>
              )}
            </button>

          </div>

          <div className="input-hint">
            <span>
              Enter to send
            </span>

            <span>
              Shift + Enter for new line
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;