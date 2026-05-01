import type {
  CreateServiceRequest,
  CreateServiceResponse,
  RollbackResponse,
  ServiceActionResponse,
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

  delete(serviceId: string) {
    return request<ServiceActionResponse>({
      method: "DELETE",
      url: `/api/services/${serviceId}?force=true&volumes=false`,
    });
  },
};
