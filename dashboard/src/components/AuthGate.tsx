import { useDashboardStore } from "@/store";
import { WelcomeModal } from "./WelcomeModal";

interface AuthGateProps {
  children: React.ReactNode;
}

export function AuthGate({ children }: AuthGateProps) {
  const { isAuthenticated } = useDashboardStore();

  if (!isAuthenticated) {
    return (
      <>
        <div className="min-h-screen bg-background" />
        <WelcomeModal open={true} />
      </>
    );
  }

  return <>{children}</>;
}
