"use client";

import { use, useEffect, useState } from "react";
import { API_URL } from "../../api";
import PublicAgentChat from "../../components/PublicAgentChat";
import type { Dealership } from "../../lib/types";

export default function EmbedWidgetPage({
  params,
}: {
  params: Promise<{ dealershipId: string }>;
}) {
  const { dealershipId } = use(params);
  const numericId = Number(dealershipId) || 0;
  const [dealershipName, setDealershipName] = useState("Dealership Showroom");
  const [isVerified, setIsVerified] = useState(true);
  const [verifying, setVerifying] = useState(true);

  useEffect(() => {
    if (!numericId) {
      setIsVerified(false);
      setVerifying(false);
      return;
    }

    let cancelled = false;
    setVerifying(true);
    fetch(`${API_URL}/dealerships/public`)
      .then((res) => (res.ok ? res.json() : []))
      .then((items: Dealership[]) => {
        if (cancelled) return;
        const match = Array.isArray(items)
          ? items.find((item) => item.id === numericId)
          : undefined;
        if (match) {
          setDealershipName(match.name);
          setIsVerified(true);
        } else {
          setIsVerified(false);
        }
      })
      .catch(() => {
        if (!cancelled) setIsVerified(false);
      })
      .finally(() => {
        if (!cancelled) setVerifying(false);
      });

    return () => {
      cancelled = true;
    };
  }, [numericId]);

  return (
    <main className="min-h-screen bg-transparent">
      <PublicAgentChat
        dealershipId={numericId}
        dealershipName={dealershipName}
        embedded
        defaultMinimized
        isVerified={isVerified}
        verifying={verifying}
      />
    </main>
  );
}
