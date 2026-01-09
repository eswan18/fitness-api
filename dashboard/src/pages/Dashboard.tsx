import {
  AllTimeStatsPanel,
  ShoeStatsPanel,
  TimePeriodStatsPanel,
  RecentRunsPanel,
} from "../panels";
import { RefreshButton } from "../components/RefreshButton";
import { MMFUploadButton } from "../components/MMFUploadButton";
import { EnvironmentIndicator } from "../components/EnvironmentIndicator";
import { StravaAuthStatusIndicator } from "../components/StravaAuthStatusIndicator";
import { GoogleAuthStatusIndicator } from "../components/GoogleAuthStatusIndicator";
import { ThemeToggle } from "../components/ThemeToggle";
import { HRSettingsPanel } from "../components/HRSettingsPanel";
import { Toaster } from "../components/ui/sonner";
import { AuthGate } from "../components/AuthGate";
import { notifySuccess, notifyInfo } from "@/lib/errors";
import type { RefreshDataResponse } from "../lib/api/fetch";
import type { UploadMmfCsvResponse } from "../lib/api/fetch";

export function Dashboard() {
  const handleRefreshComplete = (data: RefreshDataResponse) => {
    if (data.new_runs_inserted > 0) {
      notifySuccess(`Added ${data.new_runs_inserted} new runs`);
    } else {
      notifyInfo("No new runs found");
    }
  };

  const handleMmfUploadComplete = (data: UploadMmfCsvResponse) => {
    if (data.inserted_count > 0) {
      notifySuccess(`Added ${data.inserted_count} new MMF runs`);
    } else {
      notifyInfo("No new MMF runs found");
    }
  };

  return (
    <AuthGate>
      <div className="flex flex-col min-h-screen py-4 px-12 bg-background text-foreground">
        <div className="flex justify-between items-start mb-8 flex-shrink-0">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-semibold">Running Dashboard</h1>
            <EnvironmentIndicator />
            <StravaAuthStatusIndicator />
            <GoogleAuthStatusIndicator />
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <MMFUploadButton onUploadComplete={handleMmfUploadComplete} />
            <RefreshButton onRefreshComplete={handleRefreshComplete} />
          </div>
        </div>
        <div className="flex flex-row justify-between gap-x-6 mb-8 flex-shrink-0">
          <div className="flex flex-col gap-y-6 w-52 flex-grow-0">
            <AllTimeStatsPanel />
            <HRSettingsPanel />
          </div>
          <div className="flex-1 min-w-[480px]">
            <TimePeriodStatsPanel />
          </div>
          <ShoeStatsPanel className="w-96 flex-grow-0 flex-shrink-0" />
        </div>
        <div className="flex-1 min-h-0">
          <RecentRunsPanel />
        </div>
        <Toaster />
      </div>
    </AuthGate>
  );
}
