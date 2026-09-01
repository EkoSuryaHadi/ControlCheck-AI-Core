export const availabilityMessage = (section, domain) => {
  if (domain === "cost" && !section?.available) {
    return "No budget, actual cost, or commitment data was included in this import."
  }
  if (domain === "progress" && section?.source === "schedule_derived") {
    return "Progress is derived from the imported MPP schedule."
  }
  return "Data is available from the selected analysis run."
}
