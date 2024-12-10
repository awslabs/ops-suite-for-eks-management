export function getAthenaWorkGroupName(resourcePrefix: string): string {
  return `${resourcePrefix}-${"athena-workgroup"}`;
}

export function getGlueDatabaseName(resourcePrefix: string): string {
  const sanitisedPrefix = resourcePrefix.replace(/[^a-z0-9]/gi, "");
  return `${sanitisedPrefix}${"gluedatabase"}`;
}
