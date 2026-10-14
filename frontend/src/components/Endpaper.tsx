import { Icon } from "@/components/ui/Icon";
import { Polaroid } from "@/components/ui/Paper";
import { Quokka } from "@/components/ui/Quokka";

/** The endpaper: the left page of the sign-in and sign-up spreads. */
export function Endpaper() {
  return (
    <div className="stack-lg">
      <p className="eyebrow">A storybook about how you feel</p>
      <h1 className="t-title-xl">One check-in is one page.</h1>
      <p>
        A week of pages becomes a forecast for tomorrow. Every evening the book compares its
        guess with your page, and gets better at reading you.
      </p>
      <Quokka says="Hello! I'll keep you company." large size={150} />
      <Polaroid caption="cloudy, clearing by evening" tilt={-2.5}>
        <Icon name="cloud" size={56} />
      </Polaroid>
      <p className="t-caption soft">DigiBuddy is a self-reflection tool, not a medical device.</p>
    </div>
  );
}
