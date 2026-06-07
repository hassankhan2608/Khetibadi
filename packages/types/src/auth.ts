export interface User {
  id: string;
  email: string;
  name: string;
  phone?: string | null;
  created_at?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest extends LoginRequest {
  name: string;
  phone?: string;
}

export interface ProfileUpdateRequest {
  phone: string;
}

export interface AuthSession {
  access_token: string;
  token_type: "Bearer";
  expires_at: string;
  user: User;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}
