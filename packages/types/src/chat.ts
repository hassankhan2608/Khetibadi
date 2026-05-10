export type ChatRole = "user" | "assistant";
export type ChatMessageStatus = "complete" | "incomplete";

export interface ChatSession {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionCreateRequest {
  title?: string;
}

export interface ChatMessageRequest {
  message: string;
  language?: "en" | "hi";
}

export interface ChatMessage {
  id: string;
  session_id: string;
  user_id: string;
  role: ChatRole;
  content: string;
  status: ChatMessageStatus;
  created_at: string;
}

export interface KnowledgeRequest {
  title: string;
  content: string;
  source?: string;
}

export interface KnowledgeChunk {
  id: string;
  title: string;
  content: string;
  source: string;
  created_at: string;
}

export interface SSETokenEvent {
  token: string;
  index: number;
}

export interface SSEDoneEvent {
  message_id: string;
  session_id: string;
  total_tokens: number;
}

export interface SSEErrorEvent {
  error: string;
}
