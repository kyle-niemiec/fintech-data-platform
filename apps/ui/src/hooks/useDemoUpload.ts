import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { DemoUploadResponse } from "../types/api";

export function useDemoUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rows?: number) =>
      api.post<DemoUploadResponse>("/ui/demo/upload", { rows: rows ?? 25 }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.runs });
    },
  });
}
