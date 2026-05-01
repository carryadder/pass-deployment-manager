import type {
  ProjectCreateRequest,
  ProjectMemberAddRequest,
  ProjectMemberEntry,
  ProjectMemberUpdateRequest,
  ProjectSummary,
} from "../models";
import { request } from "../core/request";

export const ProjectsService = {
  list() {
    return request<ProjectSummary[]>({
      method: "GET",
      url: "/api/projects",
    });
  },

  create(payload: ProjectCreateRequest) {
    return request<ProjectSummary>({
      method: "POST",
      url: "/api/projects",
      body: payload,
    });
  },

  members(projectId: string) {
    return request<ProjectMemberEntry[]>({
      method: "GET",
      url: `/api/projects/${projectId}/members`,
    });
  },

  addMember(projectId: string, payload: ProjectMemberAddRequest) {
    return request<ProjectMemberEntry>({
      method: "POST",
      url: `/api/projects/${projectId}/members`,
      body: payload,
    });
  },

  updateMember(projectId: string, userId: string, payload: ProjectMemberUpdateRequest) {
    return request<ProjectMemberEntry>({
      method: "PATCH",
      url: `/api/projects/${projectId}/members/${userId}`,
      body: payload,
    });
  },

  removeMember(projectId: string, userId: string) {
    return request<Record<string, unknown>>({
      method: "DELETE",
      url: `/api/projects/${projectId}/members/${userId}`,
    });
  },
};
