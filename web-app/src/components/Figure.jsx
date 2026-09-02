import { useId, useState } from "react";

/**
 * Grafik sarmalayıcısı: başlık, açıklama, grafik/tablo görünüm anahtarı,
 * lejant ve kaynak notu.
 *
 * Tablo görünümü isteğe bağlı bir süs değil erişilebilirlik gereği: renk
 * körlüğü, ekran okuyucu ve yazdırma durumlarında sayılara ulaşmanın tek
 * yolu odur.
 */
export function Figure({
  title,
  caption,
  legend,
  source,
  table,
  children,
  defaultView = "chart",
}) {
  const [view, setView] = useState(defaultView);
  const id = useId();

  return (
    <figure className="figure" aria-labelledby={`${id}-title`}>
      <div className="figure__head">
        <div>
          <h3 className="figure__title" id={`${id}-title`}>
            {title}
          </h3>
          {caption && <p className="figure__caption">{caption}</p>}
        </div>
        {table && (
          <div className="segmented" role="group" aria-label="Görünüm">
            <button
              type="button"
              className="segmented__btn"
              aria-pressed={view === "chart"}
              onClick={() => setView("chart")}
            >
              Grafik
            </button>
            <button
              type="button"
              className="segmented__btn"
              aria-pressed={view === "table"}
              onClick={() => setView("table")}
            >
              Tablo
            </button>
          </div>
        )}
      </div>

      {legend && view === "chart" && <Legend items={legend} />}

      <div className="figure__body">{view === "chart" ? children : table}</div>

      {source && <figcaption className="figure__source">{source}</figcaption>}
    </figure>
  );
}

/** Renk kimliğini yazıyla eşleyen lejant. İki ve üzeri seride her zaman var. */
export function Legend({ items }) {
  return (
    <ul className="legend">
      {items.map((it) => (
        <li key={it.label} className="legend__item">
          <span
            className="legend__swatch"
            style={{ background: it.color }}
            aria-hidden="true"
          />
          <span>{it.label}</span>
        </li>
      ))}
    </ul>
  );
}

/** Basit veri tablosu — her grafiğin tablo görünümü bunu kullanır. */
export function DataTable({ columns, rows, numericFrom = 1 }) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th key={c} scope="col" className={i >= numericFrom ? "num" : ""}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri}>
              {r.map((cell, ci) =>
                ci === 0 ? (
                  <th key={ci} scope="row">
                    {cell}
                  </th>
                ) : (
                  <td key={ci} className={ci >= numericFrom ? "num" : ""}>
                    {cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
