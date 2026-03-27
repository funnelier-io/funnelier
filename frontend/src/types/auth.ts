export interface LoginRequest {
  username: string;
  password: string;
}

export interface UserResponse {
  id: string;
  tenant_id: string;
  email: string;
  username: string;
  full_name: string;
  role: string;
  is_active: boolean;
  last_login: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserResponse;
}

export interface RefreshRequest {
  refresh_token: string;
}

