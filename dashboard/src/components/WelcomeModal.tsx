import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { startOAuthFlow } from "@/lib/oauth/client";
import { notifyError } from "@/lib/errors";

interface WelcomeModalProps {
  open: boolean;
}

export function WelcomeModal({ open }: WelcomeModalProps) {
  const handleLogin = async () => {
    try {
      await startOAuthFlow();
    } catch (err) {
      notifyError(err, "Failed to start login. Please try again.");
    }
  };

  return (
    <Dialog open={open}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Welcome to Running Dashboard</DialogTitle>
          <DialogDescription>
            Track your running activities, analyze your training load, and
            monitor your progress.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Authentication is required to access your running data and manage
            your activities.
          </p>
          <Button onClick={handleLogin} className="w-full">
            Log In with OAuth
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
