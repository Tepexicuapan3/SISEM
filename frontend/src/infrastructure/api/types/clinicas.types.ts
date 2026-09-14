export interface ClinicaRefItem {
  id: string;
  name: string;
}

export interface ClinicasListResponse {
  items: ClinicaRefItem[];
  total: number;
}
