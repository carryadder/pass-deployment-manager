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

export interface ServiceEvent {
  event_id: string;
  action: string;
  created_at: string;
  actor_name?: string | null;
  details: Record<string, unknown>;
}

export interface ServiceDetailResponse {
  service_id: string;
  name: string;
  slug: string;
  image: string;
  status: string;
  project_id: string;
  project_name?: string | null;
  created_at: string;
  updated_at: string;
  domain?: string | null;
  ports: Array<{
    container_port: number;
    host_port: number | null;
  }>;
  volumes: Array<{
    source: string;
    target: string;
    mode?: "ro" | "rw";
  }>;
  network?: string | null;
  restart_policy?: string | null;
  healthcheck?: Record<string, unknown> | null;
  uptime_seconds?: number | null;
  cpu_percent?: number | null;
  memory_percent?: number | null;
  recent_events: ServiceEvent[];
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

export interface DeployResponse {
  deploy_id: string;
  service_id: string;
  status: string;
  source_type: string;
  source_ref?: string | null;
  image_tag?: string | null;
}

export interface ServiceEnvEntry {
  key: string;
  value?: string | null;
  is_secret: boolean;
  has_value: boolean;
}

export interface ServiceMetricSample {
  timestamp: string;
  cpu_percent: number;
  memory_usage_bytes: number;
  memory_limit_bytes: number;
  memory_percent: number;
  network_rx_bytes: number;
  network_tx_bytes: number;
  block_read_bytes: number;
  block_write_bytes: number;
  pids: number;
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

export interface HostDiskUsage {
  total_bytes: number;
  used_bytes: number;
  free_bytes: number;
  mountpoint: string;
}

export interface HostSummary {
  name: string | null;
  operating_system: string | null;
  architecture: string | null;
  kernel_version: string | null;
  docker_version: string | null;
  api_version: string | null;
  storage_driver: string | null;
  cgroup_version: string | null;
  cpu_count: number | null;
  memory_total_bytes: number | null;
  containers_total: number | null;
  containers_running: number | null;
  containers_paused: number | null;
  containers_stopped: number | null;
  images_total: number | null;
  disk: HostDiskUsage | null;
}

export interface ImageSummary {
  id: string;
  short_id: string;
  tags: string[];
  created: string | null;
  size: number | null;
  labels: Record<string, string>;
}

export type PruneTarget = "containers" | "images" | "volumes" | "builder";

export interface PruneRequest {
  targets: PruneTarget[];
}

export interface PruneResponse {
  containers?: { ContainersDeleted?: string[] | null; SpaceReclaimed?: number };
  images?: { ImagesDeleted?: unknown[] | null; SpaceReclaimed?: number };
  volumes?: { VolumesDeleted?: string[] | null; SpaceReclaimed?: number };
  builder_cache?: { CachesDeleted?: string[] | null; SpaceReclaimed?: number; warning?: string };
  [key: string]: unknown;
}

export interface AuditEntry {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  actor_id: string | null;
  actor_name: string | null;
  actor_email: string | null;
  created_at: string;
  details: Record<string, unknown>;
}

export interface AuditPage {
  items: AuditEntry[];
  total: number;
}

export interface AuditQuery {
  limit?: number;
  offset?: number;
  actor_id?: string;
  resource_type?: string;
  resource_id?: string;
  action?: string;
  since?: string;
  until?: string;
}

export interface RollbackResponse {
  deploy_id: string;
  status: string;
  image_tag: string;
}

export interface ServiceDeployRequest {
  git_url: string;
  branch?: string | null;
  commit?: string | null;
  dockerfile_path?: string | null;
  build_args?: Record<string, string>;
}

export interface WebhookConfigUpdateRequest {
  git_url?: string | null;
  branch?: string | null;
  dockerfile_path?: string | null;
  build_args?: Record<string, string>;
  enabled?: boolean;
}

export interface WebhookConfigResponse {
  enabled: boolean;
  url_path: string;
  token: string;
  secret: string;
  git_url: string | null;
  branch: string | null;
  dockerfile_path: string | null;
  build_args: Record<string, string>;
  last_event_at: string | null;
}

export interface TemplateEnvField {
  key: string;
  value: string | null;
  auto_secret: boolean;
  description: string | null;
}

export interface TemplateSummary {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  image: string;
  default_resources: { cpus: number; memory_mb: number };
  ports: Array<{ container_port: number; host_port?: number | null }>;
  volumes: Array<{ source: string; target: string; mode?: "ro" | "rw" }>;
  env: TemplateEnvField[];
  healthcheck: Record<string, unknown> | null;
  restart_policy: string;
  pids_limit: number | null;
}

export interface TemplateDeployRequest {
  name: string;
  cpus?: number | null;
  memory_mb?: number | null;
  domain?: string | null;
  network?: string | null;
  env_overrides?: Record<string, string>;
}

export interface TemplateDeployResponse {
  template_id: string;
  service_id: string;
  deploy_id: string;
  status: string;
  image: string;
  auto_generated_keys: string[];
}

export interface ComposePreviewRequest {
  yaml: string;
  name_prefix?: string;
}

export interface ComposePreviewService {
  name: string;
  image: string;
  cpus: number;
  memory_mb: number;
  env_keys: string[];
  port_count: number;
  volume_count: number;
  network: string | null;
  restart_policy: string;
  healthcheck: boolean;
  warnings: string[];
}

export interface ComposePreviewResponse {
  services: ComposePreviewService[];
  declared_volumes: string[];
  declared_networks: string[];
  document_warnings: string[];
  compose_path?: string | null;
}

export interface ComposeImportRequest {
  yaml: string;
  name_prefix?: string;
  only?: string[];
}

export interface ComposeRepoPreviewRequest {
  git_url: string;
  branch?: string | null;
  commit?: string | null;
  compose_path?: string | null;
  name_prefix?: string;
}

export interface ComposeRepoImportRequest {
  git_url: string;
  branch?: string | null;
  commit?: string | null;
  compose_path?: string | null;
  name_prefix?: string;
  only?: string[];
}

export interface ComposeImportedService {
  compose_name: string;
  service_name: string;
  service_id: string;
  deploy_id: string;
  image: string;
  status: string;
}

export interface ComposeImportSkipped {
  compose_name: string;
  reason: string;
}

export interface ComposeImportResponse {
  imported: ComposeImportedService[];
  skipped: ComposeImportSkipped[];
  document_warnings: string[];
  compose_path?: string | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  owner_id: string;
  owner_email: string | null;
  role: "admin" | "member" | "viewer";
  created_at: string;
  service_count: number;
  member_count: number;
}

export interface ProjectCreateRequest {
  name: string;
  description?: string | null;
}

export interface ProjectMemberEntry {
  user_id: string;
  email: string;
  full_name: string;
  role: "admin" | "member" | "viewer";
  is_owner: boolean;
  joined_at: string | null;
}

export interface ProjectMemberAddRequest {
  user_id: string;
  role: "admin" | "member" | "viewer";
}

export interface ProjectMemberUpdateRequest {
  role: "admin" | "member" | "viewer";
}

export interface InviteSummary {
  id: string;
  email: string;
  project_id: string;
  project_name: string;
  role: "admin" | "member" | "viewer";
  full_name_hint: string | null;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  accept_url: string;
  token: string;
  created_at: string;
}

export interface InviteCreateRequest {
  email: string;
  project_id: string;
  role: "admin" | "member" | "viewer";
  full_name_hint?: string | null;
  expires_in_hours?: number;
}

export interface InviteAcceptRequest {
  token: string;
  password: string;
  full_name: string;
}

export interface InvitePreviewResponse {
  email: string;
  project_id: string;
  project_name: string;
  role: "admin" | "member" | "viewer";
  full_name_hint: string | null;
  invited_by_name: string | null;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
}

export interface ServiceEnvUpsertRequest {
  key: string;
  value: string;
  is_secret?: boolean;
  apply?: boolean;
}

export interface ServiceEnvMutationResponse {
  entry: ServiceEnvEntry;
  applied: boolean;
  deploy_id?: string | null;
  service_status: string;
}
