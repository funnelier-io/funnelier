export interface LoginRequest {
  username: string;
  password: string;
}

export type UserRole = "super_admin" | "tenant_admin" | "manager" | "salesperson" | "viewer";

export interface UserResponse {
  id: string;
  tenant_id: string;
  email: string;
  username: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  is_approved: boolean;
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

export interface CreateUserRequest {
  email: string;
  username: string;
  password: string;
  full_name: string;
  role: UserRole;
}

export interface UpdateUserRequest {
  full_name?: string;
  email?: string;
  is_active?: boolean;
}

export interface ResetPasswordRequest {
  new_password: string;
}
