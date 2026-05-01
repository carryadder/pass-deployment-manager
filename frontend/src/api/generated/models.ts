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

export interface ServiceSummary {
  service_id: string;
  name: string;
  slug: string;
  image: string;
  status: string;
  project_id: string;
  created_at: string;
  updated_at: string;
  domain?: string | null;
  ports: Array<{
    container_port: number;
    host_port: number | null;
  }>;
  uptime_seconds?: number | null;
  cpu_percent?: number | null;
  memory_percent?: number | null;
}

export interface ServiceActionResponse {
  service_id: string;
  status: string;
  container_id?: string | null;
  action: string;
}

export interface CreateServiceRequest {
  name: string;
  image: string;
  cpus: number;
  memory_mb: number;
  disk_mb?: number | null;
  env?: Record<string, string>;
  ports?: Array<{ container_port: number; host_port?: number | null }>;
  volumes?: Array<{ source: string; target: string; mode?: "ro" | "rw" }>;
  network?: string | null;
  domain?: string | null;
  restart_policy?: string;
  pids_limit?: number | null;
}

export interface CreateServiceResponse {
  service_id: string;
  deploy_id: string;
  status: string;
  container_id: string;
  container_name?: string | null;
  image: string;
  project_id: string;
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

export interface RollbackResponse {
  deploy_id: string;
  status: string;
  image_tag: string;
}
