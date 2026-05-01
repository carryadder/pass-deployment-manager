export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_owner: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ContainerSummary {
  id: string;
  name: string;
  image: string;
  status: string;
  created: string;
  ports: Array<{
    container_port: string;
    host_ip: string | null;
    host_port: string | null;
  }>;
}

export interface VolumeSummary {
  name: string;
  driver: string;
  mountpoint: string;
  scope: string;
  labels: Record<string, string>;
  options: Record<string, string>;
  size_bytes: number | null;
  ref_count: number | null;
}

export interface NetworkSummary {
  id: string;
  name: string;
  short_id: string;
  driver: string;
  scope: string;
  labels: Record<string, string>;
  internal: boolean;
  attachable: boolean;
  options: Record<string, string>;
  containers: number;
}

export interface SystemInfoResponse {
  ID?: string;
  Name?: string;
  ServerVersion?: string;
  Containers?: number;
  Images?: number;
  Driver?: string;
  NCPU?: number;
  MemTotal?: number;
  OperatingSystem?: string;
  [key: string]: unknown;
}
