import type {
  TemplateDeployRequest,
  TemplateDeployResponse,
  TemplateSummary,
} from "../models";
import { request } from "../core/request";

export const TemplatesService = {
  list() {
    return request<TemplateSummary[]>({
      method: "GET",
      url: "/api/templates",
    });
  },

  detail(templateId: string) {
    return request<TemplateSummary>({
      method: "GET",
      url: `/api/templates/${encodeURIComponent(templateId)}`,
    });
  },

  deploy(templateId: string, payload: TemplateDeployRequest) {
    return request<TemplateDeployResponse>({
      method: "POST",
      url: `/api/templates/${encodeURIComponent(templateId)}/deploy`,
      body: payload,
    });
  },
};
