/** The duck piggy bank. Decorative: the app's name always stands next to it. */
export function Logo({ className = "size-8" }: { className?: string }) {
  return <img src="/logo.png" alt="" aria-hidden="true" className={`shrink-0 ${className}`} />;
}

/** Logo and name, above the forms of the signed-out pages (sign-in, invitation). */
export function Brand({ name }: { name: string }) {
  return (
    <div className="flex flex-col items-center gap-2">
      <Logo className="size-16" />
      <span className="font-display text-2xl font-black tracking-tight">{name}</span>
    </div>
  );
}
