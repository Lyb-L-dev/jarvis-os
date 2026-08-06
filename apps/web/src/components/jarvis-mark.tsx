type JarvisMarkProps = {
  className?: string;
  title?: string;
  showText?: boolean;
};

/**
 * Jarvis OS 品牌标识：J.A.R.V.I.S 黑白圆环字标（2026-08-04 定稿）。
 * 白色等宽单线正圆环，左右开口；字标水平居中穿过圆心。
 * 小尺寸场景（侧边栏、头像）建议 showText={false}，仅保留圆环。
 */
export function JarvisMark({
  className,
  title,
  showText = true,
}: JarvisMarkProps) {
  return (
    <svg
      aria-hidden={title ? undefined : true}
      className={className}
      role={title ? "img" : undefined}
      viewBox="0 0 512 512"
    >
      {title ? <title>{title}</title> : null}
      <g
        fill="none"
        stroke="currentColor"
        strokeLinecap="butt"
        strokeWidth="10"
      >
        <path d="M 107.9 232.5 A 150 150 0 0 1 404.1 232.5" />
        <path d="M 404.1 279.5 A 150 150 0 0 1 107.9 279.5" />
      </g>
      {showText ? (
        <text
          x="256"
          y="278"
          textAnchor="middle"
          fontFamily="Bahnschrift, 'Segoe UI', 'Microsoft YaHei', sans-serif"
          fontSize="62"
          fontWeight="600"
          letterSpacing="2"
          fill="currentColor"
        >
          J.A.R.V.I.S
        </text>
      ) : null}
    </svg>
  );
}
