const API_URL = "http://127.0.0.1:8000";

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface AuthUser {
  id: number;
  username: string;
  role: "user" | "admin";
}

export async function login(
  username: string,
  password: string
): Promise<LoginResponse> {
  const response = await fetch(
    `${API_URL}/api/auth/login`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        password,
      }),
    }
  );

  if (!response.ok) {
    const data = await response.json();
    throw new Error(
      data.detail || "Login failed."
    );
  }

  return response.json();
}

export async function register(
  username: string,
  password: string
): Promise<void> {
  const response = await fetch(
    `${API_URL}/api/auth/register`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        password,
      }),
    }
  );

  if (!response.ok) {
    const data = await response.json();
    throw new Error(
      data.detail || "Registration failed."
    );
  }
}

export async function getCurrentUser(
  token: string
): Promise<AuthUser> {
  const response = await fetch(
    `${API_URL}/api/auth/me`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error("Authentication failed.");
  }

  return response.json();
}

export async function sendChatMessage(
  token: string,
  sessionId: string,
  message: string
) {
  const response = await fetch(
    `${API_URL}/api/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        session_id: sessionId,
        message,
      }),
    }
  );

  if (!response.ok) {
    const data = await response.json();
    throw new Error(
      data.detail || "Chat request failed."
    );
  }

  return response.json();
}

