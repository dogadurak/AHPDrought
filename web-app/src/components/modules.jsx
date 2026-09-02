/**
 * Sayfanın bilgi hiyerarşisini kuran üç modül.
 *
 * Amaç bilgi azaltmak değil, aynı bilgiyi önem sırasına dizmek:
 *   Finding    — seviye 1: bölümün cevabı, figürden ÖNCE okunur
 *   Metric     — seviye 2: tek sayı, taranabilir
 *   Disclosure — seviye 3-4: gerekçe ve teknik ayrıntı, katlanır
 *
 * Katlanan hiçbir şey silinmez: içerik DOM'da durur, Ctrl+F bulup paneli
 * açar, yazdırmada hepsi açık basılır (App.css @media print).
 */

/** Seviye 1 — bölümün "ne bulduk" cümlesi. Bölümde en fazla bir tane. */
export function Finding({ label = "Ana bulgu", children }) {
  return (
    <div className="finding">
      <p className="finding__label">{label}</p>
      <p className="finding__text">{children}</p>
    </div>
  );
}

/** Seviye 2 — tek sayı ve ne olduğu. `sub` koşulu ya da kaynağı taşır. */
export function Metric({ value, label, sub }) {
  return (
    <div className="metric">
      <div className="metric__value">{value}</div>
      <div className="metric__label">{label}</div>
      {sub && <div className="metric__sub">{sub}</div>}
    </div>
  );
}

/** Seviye 2 — metrikleri saran ızgara; dar ekranda kendiliğinden sarar. */
export function MetricRow({ children }) {
  return <div className="metrics">{children}</div>;
}

/**
 * Seviye 3-4 — katlanır panel.
 *
 * `summary` bir etiket DEĞİL, bulgunun kendisidir: panel kapalıyken de
 * bilgi ekranda kalsın diye sayıyı ya da sonucu taşır. `hint` içeride ne
 * olduğunu söyler, böylece okur açmadan önce ne bulacağını bilir.
 */
export function Disclosure({
  id,
  summary,
  hint,
  tone = "note",
  defaultOpen = false,
  children,
}) {
  return (
    <details
      className={`disclosure disclosure--${tone}`}
      id={id}
      open={defaultOpen}
    >
      <summary className="disclosure__summary">
        <svg
          className="disclosure__chevron"
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M9 6l6 6-6 6" />
        </svg>
        <span className="disclosure__text">
          <span className="disclosure__headline">{summary}</span>
          {hint && <span className="disclosure__hint">{hint}</span>}
        </span>
      </summary>
      <div className="disclosure__body">{children}</div>
    </details>
  );
}
