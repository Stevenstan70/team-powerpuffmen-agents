import type { PricePoint } from "./api";

const W = 820;
const H = 300;
const PAD = { l: 64, r: 16, t: 16, b: 46 };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

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
    d += `${pen ? "L" : "M"}${x(i).toFixed(2)} ${y(v).toFixed(2)} `;
    pen = true;
  });
  return d;
}

// Round tick values (1, 2, 2.5 or 5 x 10^n) spanning lo..hi.
function niceTicks(lo: number, hi: number, count = 5) {
  const raw = (hi - lo) / count || 1;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = ([1, 2, 2.5, 5, 10].find((m) => m * mag >= raw) ?? 10) * mag;
  const start = Math.floor(lo / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= hi + step * 0.5; v += step) ticks.push(Number(v.toFixed(6)));
  return ticks;
}

export default function PriceChart({ series }: { series: PricePoint[] }) {
  if (series.length < 2) return null;
  const values = series.flatMap((p) =>
    [p.close, p.sma_150, p.sma_200].filter((v): v is number => v != null),
  );
  const ticks = niceTicks(Math.min(...values), Math.max(...values));
  const lo = ticks[0];
  const hi = ticks[ticks.length - 1];
  const span = hi - lo || 1;
  const x = (i: number) => PAD.l + (i * (W - PAD.l - PAD.r)) / (series.length - 1);
  const y = (v: number) => PAD.t + (1 - (v - lo) / span) * (H - PAD.t - PAD.b);
  const decimals = hi - lo < 20 ? 2 : 0;

  // One x tick at the first session of each month, labelled with year at January.
  const monthTicks = series
    .map((p, i) => ({ i, d: new Date(p.date + "T00:00:00") }))
    .filter(({ i, d }) => i === 0 || d.getMonth() !== new Date(series[i - 1].date + "T00:00:00").getMonth())
    .filter((_, k, all) => all.length <= 8 || k % 2 === 0);

  const closeLine = path(series, (p) => p.close, x, y);
  const area = `${closeLine} L${x(series.length - 1).toFixed(2)} ${y(lo)} L${x(0).toFixed(2)} ${y(lo)} Z`;

  return (
    <figure className="price-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
           aria-label="Daily closing price with 150 and 200 session averages">
        <defs>
          <linearGradient id="closeFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--teal)" stopOpacity="0.14" />
            <stop offset="100%" stopColor="var(--teal)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end">
              {t.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}
            </text>
          </g>
        ))}
        {monthTicks.map(({ i, d }) => (
          <g key={i}>
            <line x1={x(i)} x2={x(i)} y1={H - PAD.b} y2={H - PAD.b + 5} className="axis" />
            <text x={x(i)} y={H - PAD.b + 18} textAnchor="middle">
              {MONTHS[d.getMonth()]}
              {d.getMonth() === 0 || i === 0 ? ` ${String(d.getFullYear()).slice(2)}` : ""}
            </text>
          </g>
        ))}
        <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} className="axis" />
        <path d={area} fill="url(#closeFill)" stroke="none" />
        <path d={path(series, (p) => p.sma_200, x, y)} className="line sma200" />
        <path d={path(series, (p) => p.sma_150, x, y)} className="line sma150" />
        <path d={closeLine} className="line close" />
        <text className="axis-title" x={14} y={PAD.t + (H - PAD.t - PAD.b) / 2}
              transform={`rotate(-90 14 ${PAD.t + (H - PAD.t - PAD.b) / 2})`} textAnchor="middle">
          Price (provider units)
        </text>
        <text className="axis-title" x={PAD.l + (W - PAD.l - PAD.r) / 2} y={H - 6} textAnchor="middle">
          Trading day
        </text>
      </svg>
      <figcaption>
        <span className="key close" /> Daily close
        <span className="key sma150" /> 150-day average
        <span className="key sma200" /> 200-day average
        <small>Unadjusted daily closes. Averages appear once enough days are available.</small>
      </figcaption>
    </figure>
  );
}
