"use client";

import Link from "next/link";
import { OverviewBoard } from "@/components/OverviewBoard";
import { BoardSkeleton, ServiceError } from "@/components/ui";
import { useDocumentTitle, usePrefersReducedMotion, useResource } from "@/lib/hooks";
import type { OverviewPayload } from "@/lib/types";

export default function ControlRoomPage() {
  const reduced = usePrefersReducedMotion();
  const { data, error, loading, refresh } = useResource<OverviewPayload>("overview", 4000);
  useDocumentTitle("Overview");

  if (error) {
    return (
      <ServiceError
        message={error.message}
        onRetry={() => void refresh()}
        secondary={
          <Link className="btn" href="/mock">
            Open fixture preview
          </Link>
        }
      />
    );
  }

  if (!data) {
    return <BoardSkeleton />;
  }

  return <OverviewBoard data={data} reduced={reduced} loading={loading} />;
}
