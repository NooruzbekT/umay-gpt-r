/** Знак Umay: бирюзовая плитка, «галочка-сердце» и красная точка — нарисован заново для прототипа. */
export function Logo({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <rect width="40" height="40" rx="11" fill="#4DBAC0" />
      <path d="M11 19.5 18 27l11-15" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="13.5" cy="13" r="4" fill="#E5484D" />
    </svg>
  );
}
