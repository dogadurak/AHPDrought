import { useState } from "react";
import { num1, num3, pct, signed } from "../lib/format";

/* -------------------------------------------------------------------------
 * Ortak ipucu (tooltip) katmanı.
 * SVG grafiklerde işaretin üstüne gelindiğinde konumlanır. Vurgu yalnızca
 * renkle değil, ayrıca bir yüzey halkasıyla da verilir.
 * ---------------------------------------------------------------------- */

function useTooltip() {
  const [tip, setTip] = useState(null);
  const bind = (content) => ({
    onMouseEnter: (e) => {
      const host = e.currentTarget.closest(".chart-host");
      if (!host) return;
      const hb = host.getBoundingClientRect();
      const mb = e.currentTarget.getBoundingClientRect();
      setTip({
        content,
        x: mb.left - hb.left + mb.width / 2,
        y: mb.top - hb.top,
      });
    },
    onMouseLeave: () => setTip(null),
    onFocus: (e) => {
      const host = e.currentTarget.closest(".chart-host");
      if (!host) return;
      const hb = host.getBoundingClientRect();
      const mb = e.currentTarget.getBoundingClientRect();
      setTip({
        content,
        x: mb.left - hb.left + mb.width / 2,
        y: mb.top - hb.top,
      });
    },
    onBlur: () => setTip(null),
  });

  const node = tip ? (
    <div
      className="tooltip"
      style={{ left: `${tip.x}px`, top: `${tip.y}px` }}
      role="status"
    >
      {tip.content}
    </div>
  ) : null;

  return { bind, node };
}

/* -------------------------------------------------------------------------
 * 1. AHP ağırlıkları: nominal ağırlık ve efektif katkı
 *
 * İki seri, dokuz kriter. Yatay çubuk seçildi çünkü kriter adları uzun ve
 * ölçülen şey büyüklük. Efektif katkının nominal ağırlığın altında kalması
 * projenin kendi bulgusu (kriterin ölçeğinin tamamını kullanmaması), o
 * yüzden iki seri yan yana gösteriliyor.
 * ---------------------------------------------------------------------- */

export function WeightsChart({ criteria }) {
  const max = Math.max(
    ...criteria.flatMap((c) => [c.weight * 100, c.effective_pct ?? 0]),
  );
  const scale = (v) => `${(v / max) * 100}%`;

  return (
    <div className="bars">
      {criteria.map((c) => {
        const nominal = c.weight * 100;
        const eff = c.effective_pct;
        const shortfall = eff != null && nominal - eff > 1.5;
        return (
          <div className="bars__row" key={c.key}>
            <div className="bars__label">
              <span className="bars__name">{c.label}</span>
              <span className="bars__key">{c.key}</span>
            </div>
            <div className="bars__track">
              <div
                className="bars__bar bars__bar--s1"
                style={{ width: scale(nominal) }}
                title={`Nominal ağırlık: ${pct(nominal)}`}
              />
              {eff != null && (
                <div
                  className="bars__bar bars__bar--s2"
                  style={{ width: scale(eff) }}
                  title={`Efektif katkı: ${pct(eff)}`}
                />
              )}
            </div>
            <div className="bars__values">
              <span className="bars__value">{pct(nominal)}</span>
              <span
                className={`bars__value bars__value--muted${shortfall ? " is-flagged" : ""}`}
              >
                {eff == null ? "—" : pct(eff)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * 2. Risk sınıfı dağılımı
 *
 * Ordinal beş sınıf. Renkler config.yaml'daki doğrulanmış tek-hue rampadan
 * geliyor (arayüzde yeniden seçilmiyor), sıra anlam taşıdığı için.
 * ---------------------------------------------------------------------- */

export function RiskClassChart({ classes, dark }) {
  const total = classes.reduce((s, c) => s + c.share_pct, 0);
  const color = (c) => (dark ? c.color_dark : c.color);

  return (
    <div className="riskdist">
      <div
        className="riskdist__stack"
        role="img"
        aria-label={classes
          .map((c) => `${c.label} ${pct(c.share_pct)}`)
          .join(", ")}
      >
        {classes.map((c) => (
          <div
            key={c.class}
            className="riskdist__seg"
            style={{
              width: `${(c.share_pct / total) * 100}%`,
              background: color(c),
            }}
            title={`${c.label}: ${pct(c.share_pct)} · ${num1(c.area_km2)} km²`}
          />
        ))}
      </div>

      <ul className="riskdist__rows">
        {classes.map((c) => (
          <li key={c.class} className="riskdist__row">
            <span
              className="riskdist__swatch"
              style={{ background: color(c) }}
              aria-hidden="true"
            />
            <span className="riskdist__label">{c.label}</span>
            <span className="riskdist__bound">
              {c.upper_bound == null ? "" : `≤ ${num3(c.upper_bound)}`}
            </span>
            <span className="riskdist__area num">{num1(c.area_km2)} km²</span>
            <span className="riskdist__share num">{pct(c.share_pct)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * 3. Sulamanın maskeleme etkisi
 *
 * Yıl başına iki grup: kanala yakın ve kanaldan uzak tarım. Değerler sıfırın
 * iki yanına düştüğü için sıfır ekseni çizili. Kurak/yağışlı ayrımı yalnızca
 * renkle değil, eksen altındaki etiketle de veriliyor.
 * ---------------------------------------------------------------------- */

export function IrrigationChart({ rows }) {
  const { bind, node } = useTooltip();

  const W = 640;
  const H = 260;
  const M = { top: 16, right: 16, bottom: 52, left: 62 };
  const iw = W - M.left - M.right;
  const ih = H - M.top - M.bottom;

  const vals = rows.flatMap((r) => [r.near_canal, r.far_from_canal]);
  const bound = Math.max(...vals.map(Math.abs)) * 1.25;
  const y = (v) => M.top + ih / 2 - (v / bound) * (ih / 2);
  const zero = y(0);

  const groupW = iw / rows.length;
  const barW = 22;
  const gap = 6;

  const ticks = [-bound, -bound / 2, 0, bound / 2, bound];

  return (
    <div className="chart-host">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart-svg"
        role="img"
        aria-label="Kurak ve yağışlı yıllarda sulama kanalına yakın ve uzak tarım alanlarının NDVI anomalisi"
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={M.left}
              x2={M.left + iw}
              y1={y(t)}
              y2={y(t)}
              className={t === 0 ? "axis-zero" : "grid-line"}
            />
            <text x={M.left - 10} y={y(t) + 4} className="tick-label num-anchor">
              {signed(t, 3)}
            </text>
          </g>
        ))}

        {rows.map((r, i) => {
          const cx = M.left + groupW * i + groupW / 2;
          const bars = [
            {
              v: r.near_canal,
              cls: "s1",
              name: "Kanala < 2 km",
              dx: -(barW + gap) / 2,
            },
            {
              v: r.far_from_canal,
              cls: "s2",
              name: "Kanaldan > 10 km",
              dx: (barW + gap) / 2,
            },
          ];
          return (
            <g key={r.year}>
              {bars.map((b) => {
                const top = Math.min(zero, y(b.v));
                const h = Math.max(1, Math.abs(y(b.v) - zero));
                return (
                  <rect
                    key={b.cls}
                    x={cx + b.dx - barW / 2}
                    y={top}
                    width={barW}
                    height={h}
                    rx={3}
                    className={`mark mark--${b.cls}`}
                    tabIndex={0}
                    {...bind(
                      <>
                        <strong>
                          {r.year} · {b.name}
                        </strong>
                        <br />
                        NDVI anomalisi {signed(b.v)}
                      </>,
                    )}
                  />
                );
              })}
              <text x={cx} y={H - 30} className="tick-label mid">
                {r.year}
              </text>
              <text
                x={cx}
                y={H - 14}
                className={`tick-sub mid ${r.dry ? "is-dry" : ""}`}
              >
                {r.dry ? "kurak" : "yağışlı"}
              </text>
            </g>
          );
        })}
      </svg>
      {node}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * 4. Yıl bazında risk–etki korelasyonu
 *
 * Tek ölçü (Spearman ρ), işareti anlam taşıyor: negatif = modelin beklediği
 * yön. Gri bant, |ρ| < 0,2'nin bu örneklem büyüklüğünde gürültüden
 * ayrılamayacağını gösteriyor — grafiğin asıl söylediği şey bu.
 * ---------------------------------------------------------------------- */

export function RhoChart({ years }) {
  const { bind, node } = useTooltip();

  const W = 640;
  const H = 280;
  const M = { top: 16, right: 16, bottom: 56, left: 56 };
  const iw = W - M.left - M.right;
  const ih = H - M.top - M.bottom;

  const bound = 0.25;
  const y = (v) => M.top + ih / 2 - (v / bound) * (ih / 2);
  const zero = y(0);
  const NOISE = 0.2;

  const slot = iw / years.length;
  const barW = Math.min(30, slot * 0.5);
  const ticks = [-0.2, -0.1, 0, 0.1, 0.2];

  return (
    <div className="chart-host">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart-svg"
        role="img"
        aria-label="Yıl bazında risk indeksi ile gözlenen NDVI anomalisi arasındaki Spearman korelasyonu"
      >
        <rect
          x={M.left}
          y={y(NOISE)}
          width={iw}
          height={y(-NOISE) - y(NOISE)}
          className="noise-band"
        />
        <text x={M.left + 8} y={y(NOISE) + 16} className="tick-sub">
          gürültü bandı |ρ| &lt; 0,2
        </text>

        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={M.left}
              x2={M.left + iw}
              y1={y(t)}
              y2={y(t)}
              className={t === 0 ? "axis-zero" : "grid-line"}
            />
            <text x={M.left - 10} y={y(t) + 4} className="tick-label num-anchor">
              {signed(t, 1)}
            </text>
          </g>
        ))}

        {years.map((r, i) => {
          const cx = M.left + slot * i + slot / 2;
          const v = r.risk_anomaly_rho;
          const expected = v < 0;
          const top = Math.min(zero, y(v));
          const h = Math.max(1, Math.abs(y(v) - zero));
          return (
            <g key={r.year}>
              <rect
                x={cx - barW / 2}
                y={top}
                width={barW}
                height={h}
                rx={3}
                className={`mark mark--${expected ? "s1" : "s2"}`}
                tabIndex={0}
                {...bind(
                  <>
                    <strong>{r.year}</strong> · SPI {signed(r.spi, 2)}{" "}
                    {r.dry ? "(kurak)" : "(yağışlı)"}
                    <br />
                    risk–anomali ρ = {signed(v, 4)}
                    <br />
                    {expected ? "beklenen yön" : "ters yön"}
                  </>,
                )}
              />
              <text x={cx} y={H - 32} className="tick-label mid">
                {r.year}
              </text>
              {r.dry && (
                <text x={cx} y={H - 16} className="tick-sub mid is-dry">
                  kurak
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {node}
    </div>
  );
}
