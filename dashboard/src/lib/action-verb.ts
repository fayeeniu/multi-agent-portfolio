/** Short verb for the next-action button. Never “Open”. */
export function actionVerb(label: string): string {
  const text = label.replace(/\(s\)/g, "s").trim();
  if (/^resolve/i.test(text)) return "Resolve holds";
  if (/^review/i.test(text)) return "Review";
  if (/start/i.test(text)) return "Start run";
  if (/^approved/i.test(text)) return "Review";
  if (/inspect/i.test(text)) return "Inspect";
  if (/accept/i.test(text)) return "Accept identity";
  if (/advance/i.test(text)) return "Advance";
  if (/control room|workspace|open run/i.test(text)) return "Open run";
  const words = text.split(/\s+/).filter(Boolean);
  const short = words.slice(0, 2).join(" ");
  return short.length > 24 ? (words[0] ?? text) : short;
}

/** Wash colour for the next-action band. Matches the kind of work, not decoration. */
export function actionTone(label: string): "human" | "evidence" | "danger" {
  const text = label.replace(/\(s\)/g, "s").trim();
  if (/fail|inspect|withheld/i.test(text)) return "danger";
  if (/^resolve|^review|hold|await|accept/i.test(text)) return "human";
  return "evidence";
}
