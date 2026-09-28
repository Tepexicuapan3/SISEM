import { useQuery } from "@tanstack/react-query";
import { allergyAPI } from "@api/resources/allergy.api";

export const allergyKeys = {
  list: (noExp: string, pkNum: number) =>
    ["expedientes", "allergies", noExp, pkNum] as const,
};

export const useAllergies = (noExp: string, pkNum = 0) => {
  return useQuery({
    queryKey: allergyKeys.list(noExp, pkNum),
    queryFn: () => allergyAPI.list(noExp, pkNum),
    enabled: Boolean(noExp),
    staleTime: 60 * 1000,
  });
};
