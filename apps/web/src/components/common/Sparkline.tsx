type SparklineProps = {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
  className?: string;
};

/** 极简 SVG 趋势线，无依赖。 */
export function Sparkline({
  data,
  width = 120,
  height = 28,
  stroke = "var(--energy)",
  className,
}: SparklineProps) {
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = width / (data.length - 1);
  const points = data.map((value, index) => {
    const x = index * step;
    const y = height - 2 - ((value - min) / range) * (height - 6);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const line = points.join(" ");
  const area = `0,${height} ${line} ${width},${height}`;

  return (
    <svg
      aria-hidden="true"
      className={className}
      height={height}
      preserveAspectRatio="none"
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
    >
      <polygon fill={stroke} opacity="0.1" points={area} />
      <polyline
        fill="none"
        points={line}
        stroke={stroke}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.5"
      />
    </svg>
  );
}
