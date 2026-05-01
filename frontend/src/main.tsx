import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";

import AppBoot from "@/app";
import { queryClient } from "@/lib/query-client";
import "@/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppBoot />
    </QueryClientProvider>
  </React.StrictMode>,
);
