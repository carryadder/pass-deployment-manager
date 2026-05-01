import type { AuditPage, AuditQuery } from "../models";
import { request } from "../core/request";

function buildQuery(query: AuditQuery): string {
  const params = new URLSearchParams();
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  if (query.offset !== undefined) params.set("offset", String(query.offset));
  if (query.actor_id) params.set("actor_id", query.actor_id);
  if (query.resource_type) params.set("resource_type", query.resource_type);
  if (query.resource_id) params.set("resource_id", query.resource_id);
  if (query.action) params.set("action", query.action);
  if (query.since) params.set("since", query.since);
  if (query.until) params.set("until", query.until);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export const AuditService = {
  list(query: AuditQuery = {}) {
    return request<AuditPage>({
      method: "GET",
      url: `/api/audit${buildQuery(query)}`,
    });
  },
};
