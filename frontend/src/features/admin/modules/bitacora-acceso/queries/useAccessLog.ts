import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { accessLogAPI } from "@api/resources/access-log.api";
import type { AccessLogListParams } from "@api/types";

export function useAccessLog(params: AccessLogListParams) {
  return useQuery({
    queryKey: ["access-log", params],
    queryFn: () => accessLogAPI.getList(params),
    placeholderData: keepPreviousData,
  });
}
