type SystemIconProps = {
  name: string;
};

const paths: Record<string, React.ReactNode> = {
  overview: (
    <>
      <path d="M4 12 12 4l8 8" />
      <path d="M6.5 10.5V20h11v-9.5M10 20v-5h4v5" />
    </>
  ),
  chat: (
    <>
      <path d="M5 6.5h14v9H9l-4 3v-12Z" />
      <path d="M8 10h8M8 13h5" />
    </>
  ),
  growth: (
    <>
      <path d="M5 18 10 13l3 2 6-8" />
      <path d="M14 7h5v5" />
    </>
  ),
  english: (
    <>
      <path d="M5 19 10.5 5 16 19M7 14h7" />
      <path d="M17.5 8.5h2M18.5 7.5v2" />
    </>
  ),
  intelligence: (
    <>
      <circle cx="12" cy="12" r="7.5" />
      <path d="M12 7v10M7 12h10M9.2 5.2c1.7 2.3 2.4 4.5 2.4 6.8s-.7 4.5-2.4 6.8M14.8 5.2c-1.7 2.3-2.4 4.5-2.4 6.8s.7 4.5 2.4 6.8" />
    </>
  ),
  investment: (
    <>
      <path d="M5 18V9M10 18V5M15 18v-6M20 18V3" />
      <path d="M3.5 18.5h18" />
    </>
  ),
  notifications: (
    <>
      <path d="M7 17h10l-1.5-2.5V10a3.5 3.5 0 0 0-7 0v4.5Z" />
      <path d="M10 19a2.2 2.2 0 0 0 4 0M12 4V2.5" />
    </>
  ),
  memory: (
    <>
      <path d="M7 8.5A3 3 0 0 1 10 5h1v14h-1a3 3 0 0 1-3-3.5A3.8 3.8 0 0 1 5 12a3.8 3.8 0 0 1 2-3.5ZM17 8.5A3 3 0 0 0 14 5h-1v14h1a3 3 0 0 0 3-3.5 3.8 3.8 0 0 0 2-3.5 3.8 3.8 0 0 0-2-3.5Z" />
    </>
  ),
  knowledge: (
    <>
      <path d="M5 5.5h6.5a2.5 2.5 0 0 1 2.5 2.5v11a2.5 2.5 0 0 0-2.5-2.5H5ZM19 5.5h-2.5A2.5 2.5 0 0 0 14 8v11a2.5 2.5 0 0 1 2.5-2.5H19Z" />
    </>
  ),
  evaluation: (
    <>
      <path d="M5 18.5V13h4v5.5M10 18.5V9h4v9.5M15 18.5V5h4v13.5" />
      <path d="m5.5 8 3-3 2 2 4-4" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
    </>
  ),
};

export function SystemIcon({ name }: SystemIconProps) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <g
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.35"
      >
        {paths[name] || paths.overview}
      </g>
    </svg>
  );
}
