"use client";

import { OverviewBoard } from "@/components/OverviewBoard";
import { useDocumentTitle, usePrefersReducedMotion } from "@/lib/hooks";
import { OVERVIEW_MOCK } from "@/lib/overview-mock";

export default function OverviewMockPage() {
  const reduced = usePrefersReducedMotion();
  useDocumentTitle("Overview · Fixture");
  return <OverviewBoard data={OVERVIEW_MOCK} reduced={reduced} fixture />;
}
