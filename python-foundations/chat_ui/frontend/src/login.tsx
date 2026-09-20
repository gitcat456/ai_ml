import {
  useState,
  type FormEvent,
} from "react";

import {
  login,
  register,
} from "./api";

interface LoginProps {
  onLogin: (
    token: string
  ) => Promise<void>;
}

function Login({ onLogin }: LoginProps) {
  const [username, setUsername] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [isRegistering, setIsRegistering] =
    useState(false);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  async function handleSubmit(
    event: FormEvent
  ) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      if (isRegistering) {
        await register(
          username,
          password
        );
      }

      const result = await login(
        username,
        password
      );

      localStorage.setItem(
        "access_token",
        result.access_token
      );

      await onLogin(
        result.access_token
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Something went wrong."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-icon">
          AI
        </div>

        <h1>
          {isRegistering
            ? "Create account"
            : "Welcome back"}
        </h1>

        <p>
          {isRegistering
            ? "Create an account to use the AI assistant."
            : "Sign in to continue to your AI assistant."}
        </p>

        <form onSubmit={handleSubmit}>
          <div className="auth-field">
            <label>
              Username
            </label>

            <input
              type="text"
              value={username}
              onChange={(event) =>
                setUsername(
                  event.target.value
                )
              }
              placeholder="Enter username"
              required
            />
          </div>

          <div className="auth-field">
            <label>
              Password
            </label>

            <input
              type="password"
              value={password}
              onChange={(event) =>
                setPassword(
                  event.target.value
                )
              }
              placeholder="Enter password"
              required
            />
          </div>

          {error && (
            <div className="auth-error">
              {error}
            </div>
          )}

          <button
            className="auth-submit"
            type="submit"
            disabled={loading}
          >
            {loading
              ? "Please wait..."
              : isRegistering
              ? "Create account"
              : "Sign in"}
          </button>
        </form>

        <button
          className="auth-switch"
          onClick={() => {
            setIsRegistering(
              !isRegistering
            );
            setError("");
          }}
        >
          {isRegistering
            ? "Already have an account? Sign in"
            : "Need an account? Create one"}
        </button>
      </div>
    </div>
  );
}

export default Login;

