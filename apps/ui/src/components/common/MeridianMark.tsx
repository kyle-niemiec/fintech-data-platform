// The Meridian "M" mark, matching public/favicon.svg. Inline SVG so it can be
// sized and recolored where the brand appears in-app (e.g. the story callout).
export default function MeridianMark({
  size = 32,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      width={size}
      height={size}
      className={className}
      role="img"
      aria-label="Meridian"
    >
      <rect width="32" height="32" rx="6" fill="#162640" />
      <path
        d="M8 22V10h3l5 8 5-8h3v12h-2.6v-7.4L16 21h-.4l-5.4-6.4V22H8Z"
        fill="#fff"
      />
    </svg>
  );
}
