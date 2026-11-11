/** "AAAA-MM-DD" (o ISO) a "DD/MM/AAAA" sin pasar por Date: no corre el dia por zona horaria. */
export const formatPadronDate = (isoDate: string) => {
  const [year, month, day] = isoDate.slice(0, 10).split("-");
  return year && month && day ? `${day}/${month}/${year}` : isoDate;
};
