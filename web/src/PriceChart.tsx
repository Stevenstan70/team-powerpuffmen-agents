import type { PricePoint } from "./api";

const W = 800;
const H = 250;
const PAD = { l: 52, r: 14, t: 12, b: 26 };

// Draws segments only where a value exists, so an unavailable average is a gap,
// never a line from zero.
function path(points: PricePoint[], pick: (p: PricePoint) => number | null,
              x: (i: number) => number, y: (v: number) => number) {
  let d = "";
  let pen = false;
  points.forEach((p, i) => {
    const v = pick(p);
    if (v == null) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)} `;
    pen = true;
  });
  return d;
}

export default function PriceChart({ series }: { series: PricePoint[] }) {
  if (series.length < 2) return null;
  const values = series.flatMap((p) =>
    [p.close, p.sma_150, p.sma_200].filter((v): v is number => v != null),
  );
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const x = (i: number) => PAD.l + (i * (W - PAD.l - PAD.r)) / (series.length - 1);
  const y = (v: number) => PAD.t + (1 - (v - lo) / span) * (H - PAD.t - PAD.b);

  return (
    <figure className="price-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
           aria-label="Daily closing price with 150 and 200 session averages">
        <text x={PAD.l - 6} y={y(hi) + 4} textAnchor="end">{hi.toFixed(2)}</text>
        <text x={PAD.l - 6} y={y(lo) + 4} textAnchor="end">{lo.toFixed(2)}</text>
        <line x1={PAD.l} x2={W - PAD.r} y1={y(lo)} y2={y(lo)} className="axis" />
        <path d={path(series, (p) => p.sma_200, x, y)} className="line sma200" />
        <path d={path(series, (p) => p.sma_150, x, y)} className="line sma150" />
        <path d={path(series, (p) => p.close, x, y)} className="line close" />
        <text x={PAD.l} y={H - 6}>{series[0].date}</text>
        <text x={W - PAD.r} y={H - 6} textAnchor="end">{series[series.length - 1].date}</text>
      </svg>
      <figcaption>
        <span className="key close" /> Close
        <span className="key sma150" /> 150-session average
        <span className="key sma200" /> 200-session average
        <small>Unadjusted daily closes in provider units. Averages appear only once their window is complete.</small>
      </figcaption>
    </figure>
  );
}
