"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Eye, X } from "lucide-react";
import { getViewAs, exitViewAs, type ViewAsOrg } from "@/lib/viewAs";

export function ViewAsBanner() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [org, setOrg] = useState<ViewAsOrg | null>(null);

  useEffect(() => {
    const sync = () => setOrg(getViewAs());
    sync();
    window.addEventListener("viewas-change", sync);
    window.addEventListener("storage", sync); // other tabs
    return () => {
      window.removeEventListener("viewas-change", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  if (!org) return null;

  function exit() {
    exitViewAs();
    queryClient.clear(); // drop the viewed org's cached data
    router.push("/platform");
  }

  return (
    <div
      className="flex items-center justify-center gap-3 px-4 py-2 text-sm font-medium"
      style={{ background: "#7c3aed", color: "white" }}
    >
      <Eye size={15} />
      <span>
        Viewing <strong>{org.name}</strong> as platform admin — read-only
      </span>
      <button
        onClick={exit}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold"
        style={{ background: "rgba(255,255,255,0.2)" }}
      >
        <X size={13} /> Exit
      </button>
    </div>
  );
}
