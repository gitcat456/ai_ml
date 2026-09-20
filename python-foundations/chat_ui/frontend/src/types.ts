export interface Source {
  file: string | null;
  page: string | null;
  score: number | null;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  timestamp: Date;
}

export interface User {
  id: number;
  username: string;
  role: "user" | "admin";
}
