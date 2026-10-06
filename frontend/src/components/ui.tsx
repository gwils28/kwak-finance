import { type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, useId } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" };

export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...props
}: ButtonProps) {
  const look =
    variant === "primary"
      ? "bg-accent text-bg hover:opacity-90 font-semibold"
      : "border border-border bg-surface hover:border-accent";
  return (
    <button
      type={type}
      className={`rounded-md px-3 py-2 text-sm transition disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${look} ${className}`}
      {...props}
    />
  );
}

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & { label: string };

export function TextField({ label, className = "", ...props }: TextFieldProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        className={`rounded-md border border-border bg-surface px-3 py-2 focus-visible:outline-2 focus-visible:outline-accent ${className}`}
        {...props}
      />
    </div>
  );
}

export function ErrorAlert({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-md border border-negative px-3 py-2 text-sm text-negative">
      {message}
    </p>
  );
}

export function Card({
  title,
  wide = false,
  children,
}: {
  title: string;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <section
      className={`w-full ${wide ? "max-w-md" : "max-w-sm"} rounded-lg border border-border bg-surface p-6 shadow-sm`}
    >
      <h1 className="mb-4 text-2xl font-black tracking-tight">{title}</h1>
      {children}
    </section>
  );
}
