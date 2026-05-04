import type {
  ComposeImportRequest,
  ComposeImportResponse,
  ComposeRepoImportRequest,
  ComposeRepoPreviewRequest,
  ComposePreviewRequest,
  ComposePreviewResponse,
} from "../models";
import { request } from "../core/request";

export const ComposeService = {
  preview(payload: ComposePreviewRequest) {
    return request<ComposePreviewResponse>({
      method: "POST",
      url: "/api/compose/preview",
      body: payload,
    });
  },

  import(payload: ComposeImportRequest) {
    return request<ComposeImportResponse>({
      method: "POST",
      url: "/api/compose/import",
      body: payload,
    });
  },

  previewRepo(payload: ComposeRepoPreviewRequest) {
    return request<ComposePreviewResponse>({
      method: "POST",
      url: "/api/compose/preview-repo",
      body: payload,
    });
  },

  importRepo(payload: ComposeRepoImportRequest) {
    return request<ComposeImportResponse>({
      method: "POST",
      url: "/api/compose/import-repo",
      body: payload,
    });
  },
};
