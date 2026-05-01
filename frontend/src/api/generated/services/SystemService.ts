import type {
  ContainerSummary,
  NetworkSummary,
  SystemInfoResponse,
  VolumeSummary,
} from "../models";
import { request } from "../core/request";

export const SystemService = {
  systemInfo() {
    return request<SystemInfoResponse>({
      method: "GET",
      url: "/api/system/info",
    });
  },

  containers() {
    return request<ContainerSummary[]>({
      method: "GET",
      url: "/api/containers",
    });
  },

  volumes() {
    return request<VolumeSummary[]>({
      method: "GET",
      url: "/api/volumes",
    });
  },

  networks() {
    return request<NetworkSummary[]>({
      method: "GET",
      url: "/api/networks",
    });
  },
};
