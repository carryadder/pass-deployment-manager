import type {
  ContainerSummary,
  HostSummary,
  ImageSummary,
  NetworkSummary,
  PruneRequest,
  PruneResponse,
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

  host() {
    return request<HostSummary>({
      method: "GET",
      url: "/api/system/host",
    });
  },

  containers() {
    return request<ContainerSummary[]>({
      method: "GET",
      url: "/api/containers",
    });
  },

  images() {
    return request<ImageSummary[]>({
      method: "GET",
      url: "/api/images",
    });
  },

  deleteImage(imageId: string, force = false) {
    return request<Record<string, unknown>>({
      method: "DELETE",
      url: `/api/images/${encodeURIComponent(imageId)}?force=${force}`,
    });
  },

  volumes() {
    return request<VolumeSummary[]>({
      method: "GET",
      url: "/api/volumes",
    });
  },

  deleteVolume(name: string, force = false) {
    return request<Record<string, unknown>>({
      method: "DELETE",
      url: `/api/volumes/${encodeURIComponent(name)}?force=${force}`,
    });
  },

  networks() {
    return request<NetworkSummary[]>({
      method: "GET",
      url: "/api/networks",
    });
  },

  deleteNetwork(name: string) {
    return request<Record<string, unknown>>({
      method: "DELETE",
      url: `/api/networks/${encodeURIComponent(name)}`,
    });
  },

  prune(payload: PruneRequest) {
    return request<PruneResponse>({
      method: "POST",
      url: "/api/system/prune",
      body: payload,
    });
  },
};
