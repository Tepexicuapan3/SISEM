import type { DispensationQueueParams } from "@api/types";

export const dispensacionKeys = {
  all: () => ["farmacia", "dispensacion"] as const,
  queue: () => [...dispensacionKeys.all(), "queue"] as const,
  queueList: (params?: DispensationQueueParams) => [...dispensacionKeys.queue(), params ?? {}] as const,
  preview: (prescriptionId: number) => [...dispensacionKeys.all(), "preview", prescriptionId] as const,
};
