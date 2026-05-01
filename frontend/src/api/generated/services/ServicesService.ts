import type {
  CreateServiceRequest,
  CreateServiceResponse,
  DeployResponse,
  RollbackResponse,
  ServiceActionResponse,
  ServiceDeployRequest,
  ServiceDetailResponse,
  ServiceEnvEntry,
  ServiceEnvMutationResponse,
  ServiceEnvUpsertRequest,
  ServiceMetricSample,
  ServiceSummary,
} from "../models";
import { request } from "../core/request";

export const ServicesService = {
  list() {
    return request<ServiceSummary[]>({
      method: "GET",
      url: "/api/services",
    });
  },

  detail(serviceId: string) {
    return request<ServiceDetailResponse>({
      method: "GET",
      url: `/api/services/${serviceId}`,
    });
  },

  create(payload: CreateServiceRequest) {
    return request<CreateServiceResponse>({
      method: "POST",
      url: "/api/services",
      body: payload,
    });
  },

  start(serviceId: string) {
    return request<ServiceActionResponse>({
      method: "POST",
      url: `/api/services/${serviceId}/start`,
    });
  },

  stop(serviceId: string) {
    return request<ServiceActionResponse>({
      method: "POST",
      url: `/api/services/${serviceId}/stop`,
    });
  },

  restart(serviceId: string) {
    return request<ServiceActionResponse>({
      method: "POST",
      url: `/api/services/${serviceId}/restart`,
    });
  },

  redeploy(serviceId: string) {
    return request<RollbackResponse>({
      method: "POST",
      url: `/api/services/${serviceId}/redeploy`,
    });
  },

  listDeploys(serviceId: string) {
    return request<DeployResponse[]>({
      method: "GET",
      url: `/api/services/${serviceId}/deploys`,
    });
  },

  listEnv(serviceId: string) {
    return request<ServiceEnvEntry[]>({
      method: "GET",
      url: `/api/services/${serviceId}/env`,
    });
  },

  metrics(serviceId: string, range = "5m") {
    return request<ServiceMetricSample[]>({
      method: "GET",
      url: `/api/services/${serviceId}/metrics?range=${encodeURIComponent(range)}`,
    });
  },

  deployFromGit(serviceId: string, payload: ServiceDeployRequest) {
    return request<DeployResponse>({
      method: "POST",
      url: `/api/services/${serviceId}/deploy`,
      body: payload,
    });
  },

  upsertEnv(serviceId: string, payload: ServiceEnvUpsertRequest) {
    return request<ServiceEnvMutationResponse>({
      method: "POST",
      url: `/api/services/${serviceId}/env`,
      body: payload,
    });
  },

  delete(serviceId: string) {
    return request<ServiceActionResponse>({
      method: "DELETE",
      url: `/api/services/${serviceId}?force=true&volumes=false`,
    });
  },
};
