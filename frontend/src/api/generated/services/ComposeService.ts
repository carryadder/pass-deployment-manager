import type {
  ComposeImportRequest,
  ComposeImportResponse,
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
};
