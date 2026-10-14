import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { Icon, type IconName } from "./Icon";
import styles from "./Button.module.css";

type Variant = "primary" | "secondary" | "quiet";

interface CommonProps {
  variant?: Variant;
  icon?: IconName;
  iconRight?: IconName;
  block?: boolean;
  children: ReactNode;
}

export interface ButtonProps extends CommonProps, Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  loading?: boolean;
}

function classes(variant: Variant, block?: boolean, extra?: string): string {
  return [styles.button, styles[variant], block ? styles.block : "", extra ?? ""].join(" ").trim();
}

/**
 * Buttons. `primary` is the marigold rubber stamp: one per page, for the main action.
 * It sits on `shadow-stamp` and drops 3px when pressed.
 */
export function Button({
  variant = "primary",
  icon,
  iconRight,
  block,
  loading = false,
  disabled,
  children,
  className,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={classes(variant, block, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {icon ? <Icon name={icon} size={20} /> : null}
      <span>{loading ? "One moment…" : children}</span>
      {iconRight ? <Icon name={iconRight} size={20} /> : null}
    </button>
  );
}

export interface ButtonLinkProps extends CommonProps {
  href: string;
  className?: string;
}

export function ButtonLink({ variant = "secondary", icon, iconRight, block, href, children, className }: ButtonLinkProps) {
  return (
    <Link href={href} className={classes(variant, block, className)}>
      {icon ? <Icon name={icon} size={20} /> : null}
      <span>{children}</span>
      {iconRight ? <Icon name={iconRight} size={20} /> : null}
    </Link>
  );
}
