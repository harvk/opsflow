export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface AuthUser {
  id: string;
  email: string;
  full_name?: string | null;
  role: string;
  is_active: boolean;
}

export interface LoginCredentials {
  email: string;
  password: string;
}
