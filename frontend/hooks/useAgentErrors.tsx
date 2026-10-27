import { ReactNode, useEffect } from 'react';
import { toast as sonnerToast } from 'sonner';
import { useAgent, useSessionContext } from '@livekit/components-react';
import { WarningIcon } from '@phosphor-icons/react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface ToastProps {
  title: ReactNode;
  description: ReactNode;
}

export function toastAlert(toast: ToastProps) {
  const { title, description } = toast;

  return sonnerToast.custom(
    (id) => (
      <Alert onClick={() => sonnerToast.dismiss(id)} className="bg-accent w-full md:w-[364px]">
        <WarningIcon weight="bold" />
        <AlertTitle>{title}</AlertTitle>
        {description && <AlertDescription>{description}</AlertDescription>}
      </Alert>
    ),
    { duration: 10_000 }
  );
}

export function useAgentErrors() {
  const agent = useAgent();
  const { isConnected, end } = useSessionContext();

  useEffect(() => {
    if (isConnected && agent.state === 'failed') {
      const reasons = agent.failureReasons;
      // Ava hangs up on her own at the end of a call (and at the time limit), which the
      // SDK reports as the agent leaving. That's a normal ending, not an error.
      const agentHungUp = reasons.length > 0 && reasons.every((r) => /left the room/i.test(r));

      toastAlert(
        agentHungUp
          ? { title: 'Call ended', description: 'Thanks for talking to Ava.' }
          : {
              title: 'Session ended',
              description: (
                <>
                  {reasons.length > 1 && (
                    <ul className="list-inside list-disc">
                      {reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  )}
                  {reasons.length === 1 && <p className="w-full">{reasons[0]}</p>}
                </>
              ),
            }
      );

      end();
    }
  }, [agent, isConnected, end]);
}
