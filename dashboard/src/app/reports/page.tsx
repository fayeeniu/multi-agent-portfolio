"use client";

import { ReportsBoard } from "@/components/ReportsBoard";
import { BoardSkeleton, ServiceError } from "@/components/ui";
import { useDocumentTitle, useResource } from "@/lib/hooks";
import type { OverviewPayload } from "@/lib/types";

export default function ReportsPage() {
  const { data, error, refresh } = useResource<OverviewPayload>("overview");
  useDocumentTitle("Reports");

  if (error) {
    return <ServiceError message={error.message} onRetry={() => void refresh()} />;
  }

  if (!data) {
    return <BoardSkeleton />;
  }

  return <ReportsBoard data={data} />;
}
