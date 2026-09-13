import { useState } from "react";

interface Source {
  file: string | null;
  page: string | null;
  score: number | null;
}

interface ChatResponse {
  answer: string;
  sources: Source[];
}

function App() {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(false);

  async function sendMessage() {
    if (!message.trim() || loading) {
      return;
    }

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

      setAnswer(data.answer);
      setSources(data.sources);
    } catch (error) {
      console.error(error);
      setAnswer("Something went wrong while contacting the backend.");
      setSources([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>RAG Chat</h1>

      <div>
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Ask something..."
        />

        <button onClick={sendMessage} disabled={loading}>
          {loading ? "Thinking..." : "Send"}
        </button>
      </div>

      {answer && (
        <section>
          <h2>Answer</h2>
          <p>{answer}</p>

          <h3>Sources</h3>

          {sources.map((source, index) => (
            <div key={index}>
              <strong>{source.file}</strong>
              <div>Page: {source.page}</div>
              <div>Score: {source.score?.toFixed(3)}</div>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}

export default App;