// Türkçe sayı biçimlendirme. Rapor ve haritalarla aynı gösterimi kullanır:
// ondalık ayracı virgül, binlik ayracı nokta.

const nf = (min, max) =>
  new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: min,
    maximumFractionDigits: max,
  });

const f0 = nf(0, 0);
const f1 = nf(1, 1);
const f2 = nf(2, 2);
const f3 = nf(3, 3);
const f4 = nf(4, 4);

export const num = (v) => (v == null ? "—" : f0.format(v));
export const num1 = (v) => (v == null ? "—" : f1.format(v));
export const num2 = (v) => (v == null ? "—" : f2.format(v));
export const num3 = (v) => (v == null ? "—" : f3.format(v));
export const num4 = (v) => (v == null ? "—" : f4.format(v));

/** Yüzde. Rapor biçimine uyar: %11,0 (işaret önde, boşluksuz). */
export const pct = (v, digits = 1) =>
  v == null ? "—" : `%${nf(digits, digits).format(v)}`;

/** İşaretli sayı — anomali gibi yönü anlam taşıyan büyüklükler için. */
export const signed = (v, digits = 4) => {
  if (v == null) return "—";
  const s = nf(digits, digits).format(Math.abs(v));
  if (v > 0) return `+${s}`;
  if (v < 0) return `−${s}`; // U+2212, düz tire değil
  return s;
};

export const km2 = (v) => (v == null ? "—" : `${f1.format(v)} km²`);

/** ISO tarihi okunur biçime çevirir: 2026-08-31 -> 31 Ağustos 2026 */
export const isoDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("tr-TR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(d);
};
