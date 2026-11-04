export interface AuthUser {
  id: number;
  email: string;
  name: string | null;
  role: string;
}

export interface AuthOptions {
  password_enabled: boolean;
  google_enabled: boolean;
}
