import { CalendarCheckIcon } from '@phosphor-icons/react/dist/ssr';
import { Button } from '@/components/ui/button';

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div ref={ref}>
      <section className="bg-background flex flex-col items-center justify-center px-4 text-center">
        <CalendarCheckIcon aria-hidden className="text-foreground mb-4 size-16" />

        <h1 className="text-foreground text-2xl font-semibold text-balance">
          Book an appointment by voice
        </h1>
        <p className="text-muted-foreground max-w-prose pt-2 leading-6 text-pretty">
          Talk to Ava. She checks availability and adds the appointment to Google Calendar.
        </p>

        <Button
          size="lg"
          onClick={onStartCall}
          className="mt-6 w-64 rounded-full font-mono text-xs font-bold tracking-wider uppercase"
        >
          {startButtonText}
        </Button>
      </section>

      <div className="fixed bottom-5 left-0 flex w-full items-center justify-center px-4">
        <p className="text-muted-foreground max-w-prose pt-1 text-center text-xs leading-5 text-pretty md:text-sm">
          Try saying: &ldquo;I&rsquo;d like to book a haircut tomorrow at 2 PM.&rdquo;
        </p>
      </div>
    </div>
  );
};
