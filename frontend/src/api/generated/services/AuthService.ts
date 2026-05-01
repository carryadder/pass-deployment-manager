import type { LoginRequest, TokenResponse, UserResponse } from "../models";
import { request } from "../core/request";

export const AuthService = {
  login(payload: LoginRequest) {
    return request<TokenResponse>({
      method: "POST",
      url: "/api/auth/login",
      body: payload,
    });
  },

  me() {
    return request<UserResponse>({
      method: "GET",
      url: "/api/auth/me",
    });
  },
};
