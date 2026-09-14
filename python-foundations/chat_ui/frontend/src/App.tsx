import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

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
}

function App() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function sendMessage() {
    if (!message.trim() || loading) {
      return;
    }

    const userMessage: Message = {
      role: "user",
      content: message,
    };

    setMessages((previous) => [...previous, userMessage]);
    setMessage("");
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: message,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to get response");
      }

      const data: ChatResponse = await response.json();

      const assistantMessage: Message = {
        role: "assistant",
        content: data.answer,
        sources: data.sources,
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
          "Something went wrong while contacting the backend.",
      };

      setMessages((previous) => [
        ...previous,
        errorMessage,
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>RAG Assistant</h1>

          <p>
            Ask questions about your documents
          </p>
        </div>
      </header>

      <main className="chat-container">
        <div className="messages">

          {messages.length === 0 && (
            <div className="welcome">
              <h2>How can I help?</h2>

              <p>
                Ask me something about the documents
                in my knowledge base.
              </p>
            </div>
          )}

          {messages.map((msg, index) => (
            <div
              key={index}
              className={`message-row ${msg.role}`}
            >
              <div className="message">

                <div className="message-label">
                  {msg.role === "user"
                    ? "You"
                    : "Assistant"}
                </div>

                <div className="message-content">
                  {msg.role === "assistant" ? (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                </div>

                {msg.sources &&
                  msg.sources.length > 0 && (
                    <div className="sources">
                      <div className="sources-title">
                        Sources
                      </div>

                      {msg.sources.map(
                        (source, sourceIndex) => (
                          <div
                            className="source"
                            key={sourceIndex}
                          >
                            <span className="source-file">
                              {source.file}
                            </span>

                            <span>
                              Page {source.page}
                            </span>

                            <span>
                              Score{" "}
                              {source.score?.toFixed(3)}
                            </span>
                          </div>
                        )
                      )}
                    </div>
                  )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message-row assistant">
              <div className="message">

                <div className="message-label">
                  Assistant
                </div>

                <div className="typing">
                  Thinking...
                </div>

              </div>
            </div>
          )}

          <div ref={messagesEndRef} />

        </div>

        <div className="input-area">
          <textarea
            value={message}
            onChange={(event) =>
              setMessage(event.target.value)
            }
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey
              ) {
                event.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask something..."
            rows={1}
          />

          <button
            onClick={sendMessage}
            disabled={
              loading || !message.trim()
            }
          >
            {loading ? "Thinking..." : "Send"}
          </button>
        </div>
      </main>
    </div>
  );
}

export default App;