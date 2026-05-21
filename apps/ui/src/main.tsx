import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import RunsPage from "./pages/RunsPage";
import RunDetailPage from "./pages/RunDetailPage";
import DemoUploadPage from "./pages/DemoUploadPage";
import RecentTransactionsPage from "./pages/RecentTransactionsPage";
import AlertsPage from "./pages/AlertsPage";
import NotFoundPage from "./pages/NotFoundPage";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2_000,
      refetchOnWindowFocus: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<App />}>
            <Route index element={<RunsPage />} />
            <Route path="runs/:runId" element={<RunDetailPage />} />
            <Route path="demo/upload" element={<DemoUploadPage />} />
            <Route path="oltp/transactions" element={<RecentTransactionsPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
