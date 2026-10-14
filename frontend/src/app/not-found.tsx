import { Book } from "@/components/ui/Book";
import { ButtonLink } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <Book
      label="Page not found"
      left={
        <div className="stack">
          <h1 className="t-title-xl">This page isn&apos;t in the book</h1>
          <p>It may have been torn out, or it was never written.</p>
          <ButtonLink href="/" variant="primary">
            Back to today
          </ButtonLink>
        </div>
      }
    />
  );
}
