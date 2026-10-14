export function availableApplication(current: string, options: string[]): string {
  if (!Array.isArray(options) || options.length === 0) return "";
  const match = options.find((item) => String(item).toLowerCase() === String(current || "").toLowerCase());
  return match ?? options[0] ?? "";
}
