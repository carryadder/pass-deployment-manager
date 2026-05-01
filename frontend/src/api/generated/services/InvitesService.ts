import type {
  InviteAcceptRequest,
  InviteCreateRequest,
  InvitePreviewResponse,
  InviteSummary,
  TokenResponse,
} from "../models";
import { request } from "../core/request";

export const InvitesService = {
  list(projectId?: string) {
    const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    return request<InviteSummary[]>({
      method: "GET",
      url: `/api/invites${qs}`,
    });
  },

  create(payload: InviteCreateRequest) {
    return request<InviteSummary>({
      method: "POST",
      url: "/api/invites",
      body: payload,
    });
  },

  revoke(inviteId: string) {
    return request<Record<string, unknown>>({
      method: "DELETE",
      url: `/api/invites/${inviteId}`,
    });
  },

  preview(token: string) {
    return request<InvitePreviewResponse>({
      method: "GET",
      url: `/api/invites/preview/${encodeURIComponent(token)}`,
    });
  },

  accept(payload: InviteAcceptRequest) {
    return request<TokenResponse>({
      method: "POST",
      url: "/api/invites/accept",
      body: payload,
    });
  },
};
