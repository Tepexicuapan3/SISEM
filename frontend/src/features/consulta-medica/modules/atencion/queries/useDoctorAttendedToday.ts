import { useQuery } from "@tanstack/react-query";
import { visitsAPI } from "@api/resources/visits.api";
import type { DoctorAttendedTodayResponse } from "@api/types";

export const DOCTOR_ATTENDED_TODAY_KEY = ["doctor-consultation", "attended-today"] as const;

interface UseDoctorAttendedTodayOptions {
  enabled?: boolean;
}

/** Se refresca solo: la autorizacion de una receta puede resolverse mientras el medico atiende a otro. */
export const useDoctorAttendedToday = (options: UseDoctorAttendedTodayOptions = {}) => {
  return useQuery<DoctorAttendedTodayResponse>({
    queryKey: DOCTOR_ATTENDED_TODAY_KEY,
    queryFn: () => visitsAPI.getDoctorAttendedToday(),
    enabled: options.enabled ?? true,
    refetchInterval: 60_000,
  });
};
