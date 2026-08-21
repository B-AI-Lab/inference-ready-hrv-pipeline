import { useState } from "react";
import { HeartPulse } from "lucide-react";
import { HrvMultiDashboardPage } from "./hrvMulti/HrvMultiDashboardPage";

type Page = "hrv";

const TAB_NAV: Array<{ id: Page; label: string; Icon: typeof HeartPulse }> = [
  { id: "hrv",  label: "HRV Monitoring",              Icon: HeartPulse },
];

export default function App() {
  const [page, setPage] = useState<Page>("hrv");

  return (
    <>
      {/* ── Global tab bar ── */}
      <nav className="sticky top-0 z-50 border-b border-white/[0.07] bg-[#0d0920]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1800px] items-center gap-1 px-4 sm:px-6 xl:px-8">
          {TAB_NAV.map(({ id, label, Icon }) => {
            const active = page === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setPage(id)}
                className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                  active
                    ? "border-lab-electric text-white"
                    : "border-transparent text-slate-500 hover:text-slate-300"
                }`}
              >
                <Icon className={`h-4 w-4 ${active ? "text-lab-electric" : ""}`} />
                {label}
              </button>
            );
          })}
        </div>
      </nav>

      {page === "hrv"  && <HrvMultiDashboardPage />}
    </>
  );
}
