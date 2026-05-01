import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { AuthService } from "@/api/generated";
import { useAuthStore } from "@/stores/auth-store";

export function useAuthBootstrap() {
  const initialize = useAuthStore((state) => state.initialize);
  const hydrated = useAuthStore((state) => state.hydrated);
  const accessToken = useAuthStore((state) => state.accessToken);
  const setCurrentUser = useAuthStore((state) => state.setCurrentUser);
  const logout = useAuthStore((state) => state.logout);

  useEffect(() => {
    initialize();
  }, [initialize]);

  const meQuery = useQuery({
    queryKey: ["auth", "me", accessToken],
    queryFn: AuthService.me,
    enabled: hydrated && !!accessToken,
    retry: false,
  });

  useEffect(() => {
    if (meQuery.data) {
      setCurrentUser(meQuery.data);
    }
  }, [meQuery.data, setCurrentUser]);

  useEffect(() => {
    if (meQuery.isError) {
      logout();
    }
  }, [logout, meQuery.isError]);

  return {
    hydrated,
    isLoading: !hydrated || (!!accessToken && meQuery.isLoading),
  };
}
