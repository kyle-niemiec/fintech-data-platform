import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { DemoUploadResponse } from "../types/api";

export function useDemoUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { rows?: number; valid?: boolean }) =>
      api.post<DemoUploadResponse>("/ui/demo/upload", {
        rows: vars.rows ?? 25,
        valid: vars.valid ?? true,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.runs });
    },
  });
}
