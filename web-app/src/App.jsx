import { useEffect, useState } from "react";
import { DataTable, Figure } from "./components/Figure";
import {
  IrrigationChart,
  RhoChart,
  RiskClassChart,
  WeightsChart,
} from "./components/charts";
import { Disclosure, Finding, Metric, MetricRow } from "./components/modules";
import { RiskMap } from "./components/RiskMap";
import { isoDate, km2, num, num1, num2, num4, pct, signed } from "./lib/format";
import "./App.css";

const REPO = "https://github.com/dogadurak/AHPDr";

const SECTIONS = [
  { id: "harita", label: "Risk haritası" },
  { id: "agirliklar", label: "AHP ağırlıkları" },
  { id: "sulama", label: "Sulama etkisi" },
  { id: "dogrulama", label: "Doğrulama" },
  { id: "yontem", label: "Yöntem" },
];

/* --- tema ---------------------------------------------------------------
 * Üç durum: sistem (varsayılan, kök üzerinde işaret yok), açık, koyu.
 * Seçim localStorage'da tutulur; erişilemediği durumda (gizli pencere,
 * site verisi kapalı) sistem ayarına düşer.
 */
function useTheme() {
  const [choice, setChoice] = useState(() => {
    try {
      return localStorage.getItem("theme") ?? "system";
    } catch {
      return "system";
    }
  });

  useEffect(() => {
    const root = document.documentElement;
    if (choice === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", choice);
    try {
      localStorage.setItem("theme", choice);
    } catch {
      /* kalıcılık olmadan da çalışır */
    }
  }, [choice]);

  // Grafikler koyu/açık varyantı seçebilsin diye çözümlenmiş durum.
  const [systemDark, setSystemDark] = useState(
    () => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false,
  );
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mq) return;
    const onChange = (e) => setSystemDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const dark = choice === "dark" || (choice === "system" && systemDark);
  return { choice, setChoice, dark };
}

function ThemeToggle({ choice, setChoice }) {
  const next = { system: "light", light: "dark", dark: "system" }[choice];
  const label = { system: "Sistem", light: "Açık", dark: "Koyu" }[choice];
  const icon = { system: "◐", light: "☀", dark: "☾" }[choice];
  return (
    <button
      type="button"
      className="ghost-btn"
      onClick={() => setChoice(next)}
      aria-label={`Tema: ${label}. Değiştirmek için tıklayın.`}
      title={`Tema: ${label}`}
    >
      <span aria-hidden="true">{icon}</span> {label}
    </button>
  );
}

/* --- veri ---------------------------------------------------------------- */

function useSummary() {
  const [state, setState] = useState({ status: "loading" });

  useEffect(() => {
    let alive = true;
    fetch(`${import.meta.env.BASE_URL}data/summary.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => alive && setState({ status: "ready", data }))
      .catch((error) => alive && setState({ status: "error", error }));
    return () => {
      alive = false;
    };
  }, []);

  return state;
}

/* --- katlanır panellerin iki kenar durumu --------------------------------
 * 1) Derin bağlantı: bir çapa katlanmış panelin İÇİNDEyse panel açılmalı,
 *    yoksa bağlantı boş bir yere kaydırır.
 * 2) Yazdırma: kâğıtta katlama diye bir şey yok. CSS bunu zaten açıyor
 *    ama tarayıcılar <details> içeriğini farklı gizliyor; beforeprint ile
 *    gerçekten açıp sonra eski haline döndürmek tek güvenilir yol.
 */
function useDisclosureEdgeCases(ready) {
  useEffect(() => {
    if (!ready) return;

    const openAncestors = () => {
      const id = decodeURIComponent(window.location.hash.slice(1));
      if (!id) return;
      const target = document.getElementById(id);
      if (!target) return;
      for (let node = target; node; node = node.parentElement) {
        if (node.tagName === "DETAILS") node.open = true;
      }
      target.scrollIntoView();
    };

    let reclosed = [];
    const openAll = () => {
      reclosed = [...document.querySelectorAll("details:not([open])")];
      for (const d of reclosed) d.open = true;
    };
    const restore = () => {
      for (const d of reclosed) d.open = false;
      reclosed = [];
    };

    openAncestors();
    window.addEventListener("hashchange", openAncestors);
    window.addEventListener("beforeprint", openAll);
    window.addEventListener("afterprint", restore);
    return () => {
      window.removeEventListener("hashchange", openAncestors);
      window.removeEventListener("beforeprint", openAll);
      window.removeEventListener("afterprint", restore);
    };
  }, [ready]);
}

/* --- küçük parçalar ------------------------------------------------------ */

function Stat({ value, label, sub }) {
  return (
    <div className="stat">
      <div className="stat__value">{value}</div>
      <div className="stat__label">{label}</div>
      {sub && <div className="stat__sub">{sub}</div>}
    </div>
  );
}

function Section({ id, eyebrow, title, lead, children }) {
  return (
    <section className="section" id={id}>
      <header className="section__head">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2 className="section__title">{title}</h2>
        {lead && <p className="section__lead">{lead}</p>}
      </header>
      {children}
    </section>
  );
}

/* --- sayfa --------------------------------------------------------------- */

export default function App() {
  const { choice, setChoice, dark } = useTheme();
  const state = useSummary();
  useDisclosureEdgeCases(state.status === "ready");

  if (state.status === "loading") {
    return (
      <div className="boot" role="status">
        <span className="spinner" aria-hidden="true" />
        Analiz özeti yükleniyor…
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="boot boot--error" role="alert">
        <h1>Özet verisi okunamadı</h1>
        <p>
          <code>public/data/summary.json</code> bulunamadı. Üretmek için proje
          kökünde:
        </p>
        <pre>python -m scripts.export_web_data</pre>
        <p className="note">{String(state.error)}</p>
      </div>
    );
  }

  const d = state.data;
  const cls = d.classification;
  const criteria = d.ahp.criteria;
  const veryHigh = cls.classes.at(-1);
  const base = import.meta.env.BASE_URL;

  return (
    <>
      <a className="skip-link" href="#harita">
        İçeriğe geç
      </a>

      <header className="topbar">
        <div className="topbar__inner">
          <a className="brand" href="#top">
            <span className="brand__mark" aria-hidden="true" />
            <span className="brand__text">
              <strong>Gediz Kuraklık Riski</strong>
              <span>AHP · 9 kriter · 30 m</span>
            </span>
          </a>

          <nav className="topbar__nav" aria-label="Bölümler">
            {SECTIONS.map((s) => (
              <a key={s.id} href={`#${s.id}`}>
                {s.label}
              </a>
            ))}
          </nav>

          <div className="topbar__actions">
            <ThemeToggle choice={choice} setChoice={setChoice} />
            <a className="ghost-btn" href={REPO} rel="noreferrer noopener">
              GitHub
            </a>
          </div>
        </div>
      </header>

      <main id="top">
        {/* --- Hero --- */}
        <section className="hero">
          <div className="hero__inner">
            <p className="eyebrow">
              Çok kriterli karar verme · Uzaktan algılama · {d.scenario}
            </p>
            <h1 className="hero__title">
              Tarımsal kuraklık riski,
              <br />
              Gediz Havzası
            </h1>
            <p className="hero__lead">
              Analitik Hiyerarşi Süreci ile dokuz kriterden kurulan 30 m
              çözünürlüklü risk haritası — ve haritanın bağımsız gözlemle
              sınanması. Sınama, modelin gözlenen kuraklık etkisini{" "}
              <strong>öngörmediğini</strong> gösterdi; sayfa bu sonucu da
              raporluyor.
            </p>

            <div className="hero__stats">
              <Stat
                value={km2(cls.total_area_km2)}
                label="Sınıflandırılan alan"
                sub={`${num(d.grid.resolution_m)} m grid · ${d.grid.crs}`}
              />
              <Stat
                value={String(d.ahp.n_criteria)}
                label="AHP kriteri"
                sub={`CR = ${num4(d.ahp.consistency_ratio)} (eşik ${num2(d.ahp.cr_threshold)})`}
              />
              <Stat
                value={pct(veryHigh.share_pct)}
                label="Çok yüksek risk"
                sub={km2(veryHigh.area_km2)}
              />
              <Stat
                value="68 yıl"
                label="İklim serisi"
                sub="TerraClimate 1958–2025"
              />
            </div>
          </div>
        </section>

        {/* --- Harita --- */}
        <Section
          id="harita"
          eyebrow="Adım 4–5"
          title="Risk haritası"
          lead="Risk indeksi Jenks doğal kırılımlarıyla beş sınıfa ayrıldı. Haritadaki katman ve yanındaki bütün paylar aynı raster'dan sayılıyor — figürden ya da rapordan değil."
        >
          <RiskMap
            overlay={
              d.map_overlay
                ? { ...d.map_overlay, url: `${base}${d.map_overlay.url}` }
                : null
            }
            overlayRf={
              d.map_overlay_rf
                ? { ...d.map_overlay_rf, url: `${base}${d.map_overlay_rf.url}` }
                : null
            }
            classes={cls.classes}
            dark={dark}
            fallbackImage={`${base}figures/risk_map_steep_riskier.png`}
          />

          <Finding>
            Sulama erişimi kritere eklenince risk zirvesi ova tabanından yamaç
            eteğine kaydı; tarımın ortalama riski meranın altına indi (0,395 ve
            0,439).
          </Finding>

          <Figure
            title="Risk sınıfı dağılımı"
            caption={`Jenks doğal kırılımları · ${cls.n_classes} sınıf · toplam ${km2(cls.total_area_km2)}`}
            source={
              <>
                {cls.masked && (
                  <>
                    Maskeli alan (yerleşim, su yüzeyi, veri boşluğu):{" "}
                    {km2(cls.masked.area_km2)} — sınıflandırmaya girmedi.
                    <br />
                  </>
                )}
                Paylar <code>{cls.source_raster}</code> dosyasından sayıldı.
                {cls.report_is_stale && (
                  <>
                    {" "}
                    Sınıf sınırları gösterilmiyor: <code>
                      outputs/reports/ahp_{d.scenario}.md
                    </code>{" "}
                    bu raster'dan eski.
                  </>
                )}
              </>
            }
            table={
              <DataTable
                columns={["Sınıf", "Üst sınır", "Piksel", "Alan (km²)", "Pay"]}
                rows={cls.classes.map((c) => [
                  c.label,
                  c.upper_bound == null ? "—" : num4(c.upper_bound),
                  num(c.pixels),
                  num1(c.area_km2),
                  pct(c.share_pct),
                ])}
              />
            }
          >
            <RiskClassChart classes={cls.classes} dark={dark} />
          </Figure>

          <Disclosure
            id="harita-sulama"
            summary="Sulamanın eklenmesi haritayı fiziksel olarak değiştirdi"
            hint="yedi kriterli sürümle karşılaştırma"
          >
            <p>
              Yedi kriterli sürümde tarım ve mera <em>aynı</em> riskte çıkıyor,
              en riskli yer ova tabanı oluyordu. Sulama erişimi eklenince tarımın
              ortalama riski meranın altına indi (0,395 ve 0,439) ve risk zirvesi
              ova tabanından 563–860 m yamaç eteğine kaydı.
            </p>
            <p>
              Sebep fiziksel: Gediz ovası sıcak ve kurak, ama{" "}
              <strong>sulanıyor</strong>. Yamaç etekleri hem kurak hem şebeke
              dışında.
            </p>
          </Disclosure>

          {d.map_overlay_rf && (
            <Disclosure
              id="harita-rf"
              summary="Haritanın yanında ikinci bir model var: Random Forest tahmini"
              hint="katman denetiminden açılır — neden ikisi de gösteriliyor"
            >
              <p>
                Üstteki katman denetiminden{" "}
                <strong>Random Forest tahmini</strong> açılabilir. Bu harita AHP
                ağırlıklarıyla değil, Adım 14'te eğitilen modelin öngördüğü NDVI
                anomalisinden üretilir; aynı paleti ve aynı beş sınıfı kullanır.
              </p>
              <p>
                İkisi aynı şeyi ölçmüyor: AHP haritası{" "}
                <em>fiziksel duyarlılık nerede yüksek</em> sorusunu, RF haritası{" "}
                <em>gözlenen stres nerede yüksek çıkıyor</em> sorusunu
                yanıtlıyor. Birbirini tutmamaları bu projenin bulgusu — fiziksel
                değişkenler gözlenen stresin yalnızca küçük bir kısmını
                açıklıyor (R² = 0,133, mekânsal blok çapraz doğrulama).
              </p>
              <p>
                RF haritası bir süre AHP haritasının dosyalarının üstüne
                yazıyordu ve sayfa onu AHP haritası sanarak gösteriyordu. Çıktı
                adları artık ayrı; ikisi yan yana, hangisinin hangisi olduğu
                yazılı duruyor.
              </p>
            </Disclosure>
          )}

          <Disclosure
            id="harita-duyarlilik"
            tone="warn"
            summary="Duyarlılık analizi: en kötü senaryoda piksellerin %93,1'i aynı sınıfta kalıyor"
            hint="her ağırlık ±%10 oynatıldığında"
          >
            <p>
              Her ağırlık ±%10 oynatıldığında aynı sınıfta kalan piksel oranı en
              kötü <strong>%93,1</strong> (yağış −%10), en iyi %99,3 (bakı).
              Spearman sıra korelasyonu hiçbir senaryoda 0,997'nin altına
              inmiyor.
            </p>
          </Disclosure>
        </Section>

        {/* --- Ağırlıklar --- */}
        <Section
          id="agirliklar"
          eyebrow="Adım 1"
          title="AHP ağırlıkları ve efektif katkı"
          lead="Ağırlıklar 9×9 ikili karşılaştırma matrisinden özvektör yöntemiyle türetildi. Nominal ağırlık, kriterin ölçeğinin tamamını kullandığı varsayımıyla anlam taşır; kullanmayan kriter haritada beklenenden az ayrım üretir."
        >
          <Finding>
            Nominal ağırlık her zaman ayrım demek değil: suya uzaklık kriteri
            %5,2 ağırlığa sahip ama haritadaki efektif katkısı yalnızca %2,6.
          </Finding>

          <Figure
            title="Nominal ağırlık ve efektif katkı"
            caption="Efektif katkı = ağırlıkla çarpılmış değerlerin standart sapma payı."
            legend={[
              { label: "Nominal AHP ağırlığı", color: "var(--series-1)" },
              { label: "Efektif katkı", color: "var(--series-2)" },
            ]}
            source={`λmax = ${num4(d.ahp.lambda_max)} · CI = ${num4(d.ahp.consistency_index)} · CR = ${num4(d.ahp.consistency_ratio)} (eşik ${num2(d.ahp.cr_threshold)})`}
            table={
              <DataTable
                columns={[
                  "Kriter",
                  "Ağırlık",
                  "Efektif katkı",
                  "Kullanılan aralık",
                  "Kaynak",
                ]}
                rows={criteria.map((c) => [
                  c.label,
                  num4(c.weight),
                  c.effective_pct == null ? "—" : pct(c.effective_pct),
                  c.used_range
                    ? `${num2(c.used_range[0])}–${num2(c.used_range[1])}`
                    : "—",
                  c.source?.collection ?? c.source?.provider ?? "—",
                ])}
              />
            }
          >
            <WeightsChart criteria={criteria} />
          </Figure>

          <Disclosure
            id="agirliklar-neden"
            summary="Ağırlık ile katkı neden ayrışıyor?"
            hint="suya uzaklık kriterinin havzadaki değişkenliği"
          >
            <p>
              <code>distance_to_water</code> nominal %5,2 ağırlığa sahip ama
              efektif katkısı yalnızca %2,6. Sebep: havzadaki 728 km'lik akarsu
              ağı yüzünden alanın %90'ı suya yakın, skorlar 0–0,74 bandına
              sıkışıyor. Kriterin ölçeği var, havzadaki değişkenliği yok.
            </p>
          </Disclosure>
        </Section>

        {/* --- Sulama --- */}
        {d.irrigation_effect?.length > 0 && (
          <Section
            id="sulama"
            eyebrow="Adım 11"
            title="Sulama, NDVI'daki kuraklık sinyalini maskeliyor"
            lead="Kurak yıllarda tarım alanı NDVI anomalisi, sulama şebekesine olan mesafeye göre ayrıştırıldı. Fark yalnızca stres varken ortaya çıkıyor — yağışlı yılda iki grup arasında fark yok."
          >
            <Finding>
              Yağmura bağlı tarım, kurak yıllarda sulanan tarımdan 2–10 kat fazla
              NDVI kaybediyor.
            </Finding>

            <Figure
              title="Kanala uzaklığa göre NDVI anomalisi"
              caption="Yalnızca tarım alanı (ESA WorldCover sınıf 40)."
              legend={[
                { label: "Kanala < 2 km", color: "var(--series-1)" },
                { label: "Kanaldan > 10 km", color: "var(--series-2)" },
              ]}
              source="Kaynak: outputs/reports/operational_test.md"
              table={
                <DataTable
                  columns={["Yıl", "Durum", "Kanala < 2 km", "Kanaldan > 10 km"]}
                  rows={d.irrigation_effect.map((r) => [
                    String(r.year),
                    r.condition,
                    signed(r.near_canal),
                    signed(r.far_from_canal),
                  ])}
                />
              }
            >
              <IrrigationChart rows={d.irrigation_effect} />
            </Figure>

            <Disclosure
              id="sulama-dogrulama"
              tone="good"
              summary="Bu, sulama kriterinin bağımsız doğrulaması"
              hint="yağışlı 2023 yılıyla karşılaştırma"
            >
              <p>
                Yağmura bağlı tarım, kurak yıllarda sulanan tarımdan{" "}
                <strong>2–10 kat</strong> fazla NDVI kaybediyor. Yağışlı yılda
                (2023) iki grup arasında fark yok — yani ölçülen şey arazi farkı
                değil, sulamanın stres altındaki koruyucu etkisi.
              </p>
            </Disclosure>

            <Disclosure
              id="sulama-metodoloji"
              tone="warn"
              summary="Sulanan bir havzada NDVI, tarımsal kuraklık etkisini ölçemez"
              hint="metodolojik sonuç"
            >
              <p>
                <strong>
                  Sulanan bir havzada NDVI, tarımsal kuraklık etkisini ölçemez.
                </strong>{" "}
                Çiftçi sularsa yeşillik korunur; etki suya, maliyete ve rezervuar
                seviyesine yansır, spektruma değil.
              </p>
            </Disclosure>
          </Section>
        )}

        {/* --- Doğrulama / negatif sonuç --- */}
        <Section
          id="dogrulama"
          eyebrow="Adım 13 · negatif sonuç"
          title="Harita gözlenen etkiyi öngörmüyor"
          lead="Model bütün iç tutarlılık ölçütlerini geçiyor. Ama iç tutarlılık geçerlilik değildir: harita, kuraklıkta bitki örtüsünün nerede zarar göreceğini bilmiyor. Bu sayfanın gizlemek yerine raporladığı sonuç budur."
        >
          <h3 className="block-title">Geçtiği sınamalar</h3>
          <MetricRow>
            <Metric
              value={num4(d.ahp.consistency_ratio)}
              label="Tutarlılık oranı (CR)"
              sub={`eşik ${num2(d.ahp.cr_threshold)}`}
            />
            <Metric
              value="%99,7"
              label="k-means uyumu"
              sub="bağımsız sınıflandırma"
            />
            <Metric
              value="%93,1"
              label="Ağırlık duyarlılığı"
              sub="en kötü senaryoda aynı sınıfta kalan piksel"
            />
            <Metric
              value="%79,4"
              label="Senaryo dayanıklılığı"
              sub="aynı sınıfta; %100'ü en fazla 1 sınıf kayıyor"
            />
            <Metric
              value="−0,283"
              label="ET/PET ile monoton sıralama"
              sub="ρ · bağımsız MODIS ürünü"
            />
          </MetricRow>

          <div className="verdict-fail">
            <h3 className="block-title">Geçemediği sınama</h3>
            <ul>
              <li>
                Landsat 5 ile <strong>27 yıl, 7 gerçek kurak yıl</strong>{" "}
                (1985–2011): kurak yıl ρ = <strong>−0,023</strong> — sıralama yok
              </li>
              <li>
                İkinci, bağımsız etki ölçüsü ET/PET ile de aynı sonuç (ρ ={" "}
                <strong>+0,045</strong>)
              </li>
              <li>
                Üçüncü ölçü — Landsat yüzey sıcaklığı, enerji dengesi yolu — yine
                aynı (ρ = <strong>+0,044</strong>)
              </li>
              <li>
                “Düşük değişkenlikli kriterler bozuyor” hipotezi kuruldu ve{" "}
                <strong>reddedildi</strong> (ρ −0,023 → +0,013)
              </li>
              <li>
                Random Forest ile fiziksel taban çizgisi: R² ≈{" "}
                <strong>0,13</strong> (mekânsal blok CV)
              </li>
            </ul>
          </div>

          {d.operational_years?.length > 0 && (
            <Figure
              title="Yıl bazında risk–etki korelasyonu"
              caption="Spearman ρ, risk indeksi ile gözlenen NDVI anomalisi arasında. Yalnızca tarım alanı, ham fark."
              legend={[
                { label: "Beklenen yön (ρ < 0)", color: "var(--series-1)" },
                { label: "Ters yön (ρ > 0)", color: "var(--series-2)" },
              ]}
              source="Kaynak: outputs/reports/operational_test.md — Sentinel-2 dönemi (2017–2025)."
              table={
                <DataTable
                  columns={["Yıl", "SPI", "Durum", "Ort. anomali", "ρ"]}
                  rows={d.operational_years.map((r) => [
                    String(r.year),
                    signed(r.spi, 2),
                    r.dry ? "kurak" : "yağışlı",
                    signed(r.mean_anomaly, 3),
                    signed(r.risk_anomaly_rho),
                  ])}
                />
              }
            >
              <RhoChart years={d.operational_years} />
            </Figure>
          )}

          <Disclosure
            id="dogrulama-katki"
            summary="Bu neden bir katkı, kusur değil"
            hint="dört çıkarım ve kalan en makul açıklama"
          >
            <p>
              Literatürdeki AHP kuraklık haritalarının büyük kısmı duyarlılık
              analizinde durur; gözlenen etkiyle karşılaştırma yapmaz. Bu proje o
              adımı attı ve olumsuz sonucu raporluyor. Dört çıkarım:
            </p>
            <ol>
              <li>
                <strong>İç tutarlılık, geçerlilik değildir.</strong> CR, k-means
                ve duyarlılık analizinin hepsini geçen bir harita gözlenen etkiyi
                öngörmeyebilir.
              </li>
              <li>
                <strong>Sonuç ölçü seçimine bağlı değil.</strong> Üç bağımsız
                etki ölçüsü — yeşillik, su kısıtı, yüzey sıcaklığı — üç farklı
                fiziksel yol, aynı cevap.
              </li>
              <li>
                <strong>Sonuç kriter seçimine de bağlı değil.</strong> Neredeyse
                sabit kriterleri çıkarıp yeniden ağırlıklandırmak düzeltmedi.
              </li>
              <li>
                <strong>
                  Doğrulama, uydu arşivinin kapsadığı dönemle sınırlıdır.
                </strong>{" "}
                Havzanın gerçek kuraklıkları Sentinel-2'den önce; Landsat olmasa
                test hiç yapılamazdı.
              </li>
            </ol>
            <p>
              Geriye kalan en makul açıklama (bu projede sınanamadı): 30 m
              ölçekte kuraklık etkisini belirleyen şey fiziksel duyarlılıktan çok{" "}
              <strong>parsel düzeyi yönetim kararlarıdır</strong> — hangi ürün
              ekildiği, sulanıp sulanmadığı, kuyu erişimi.
            </p>
          </Disclosure>
        </Section>

        {/* --- Yöntem --- */}
        <Section
          id="yontem"
          eyebrow="Yöntem"
          title="Veri kaynakları ve sınırlılıklar"
          lead="Hiçbir veri kaynağı API anahtarı gerektirmiyor. Hiçbir ağırlık, eşik, sınıf skoru veya renk kod içine gömülü değil — hepsi config.yaml veya lookups/ içinden geliyor."
        >
          {/* Sınırlılıklar bilerek açık: bir risk haritasının en kolay kötüye
              kullanılacak yeri, sınırları okunmadan haritaya bakılmasıdır. */}
          <div className="panel">
            <h3 className="panel__title">Bilinen sınırlılıklar</h3>
            <ol className="limits">
              <li>
                <strong>Sulama katmanı bir vekildir.</strong> OSM kanal ağından
                türetiliyor; DSİ'nin resmî komuta alanı değil. Tersiyer şebeke
                eksik.
              </li>
              <li>
                <strong>Matris uzman anketiyle kurulmadı.</strong> Literatür
                sıralamasına dayanan bir başlangıç seti. Anket aracı hazır (
                <code>scripts/ahp_survey.py</code>), anket yapılmadı.
              </li>
              <li>
                <strong>Saha verisiyle doğrulama yok.</strong> TÜİK / DSİ / MGM
                kaynaklarının açık API'si yok.
              </li>
              <li>
                <strong>Ölçek uyumsuzluğu.</strong> Yağış ~5,5 km, LST 1 km,
                toprak 250 m katmanları 30 m grid'e yeniden örnekleniyor —
                sonuçlar 30 m hassasiyetinde yorumlanmamalı.
              </li>
              <li>
                <strong>NDVI kısmen döngüsel.</strong> Hem girdi kriteri hem
                doğrulama ekseni; doğrulama bu yüzden seviye yerine mevsimsel
                genlik kullanıyor.
              </li>
            </ol>
          </div>

          <Disclosure
            id="yontem-kaynaklar"
            summary={`${d.ahp.n_criteria} kriterin veri kaynakları`}
            hint="sağlayıcı ve koleksiyon tablosu"
          >
            <DataTable
              columns={["Kriter", "Sağlayıcı", "Koleksiyon"]}
              numericFrom={99}
              rows={criteria.map((c) => [
                c.label,
                c.source?.provider ?? "—",
                c.source?.collection ?? "—",
              ])}
            />
          </Disclosure>

          <Disclosure
            id="yontem-hatalar"
            summary="Yolda bulunan ve düzeltilen sekiz veri hatası"
            hint="hiçbiri hata vermeden, sessizce yanlış sonuç üretecekti"
          >
            <p>
              Hiçbiri hata vermeden, sessizce yanlış sonuç üretecekti: Sentinel-2
              baseline 04.00 radyometrik offset'i (2022 sonrası ~0,13 düşük
              NDVI), yanlış UTM zone (32636 → 32635), MODIS koleksiyonunun Terra
              ve Aqua platformlarını karıştırması, senaryo kriterlerinin aynı
              dosyayı paylaşması, Jenks sınıflandırmasının tohumlanmamış olması,
              sulama kriterinin sabit tavana yapışması (%68,9 alan), Overpass ağ
              hatalarının kısmi ağ üretmesi ve sistem genelindeki PROJ çakışması.
            </p>
            <p>
              Tamamı gerekçesiyle{" "}
              <a href={`${REPO}#yol-boyunca-bulunan-ve-düzeltilen-veri-hataları`}>
                README'de belgelenmiş
              </a>
              .
            </p>
          </Disclosure>
        </Section>
      </main>

      <footer className="footer">
        <div className="footer__inner">
          <div>
            <strong>{d.project.name}</strong>
            <p className="note">
              {d.project.aoi_name} · sürüm {d.project.version} · senaryo{" "}
              <code>{d.scenario}</code>
            </p>
          </div>
          <div className="footer__meta">
            <p className="note">
              Veri özeti {isoDate(d.generated)} tarihinde{" "}
              <code>scripts/export_web_data.py</code> ile üretildi.
            </p>
            <p className="note">
              <a href={REPO} rel="noreferrer noopener">
                Kaynak kodu
              </a>{" "}
              · MIT lisansı
            </p>
          </div>
        </div>
      </footer>
    </>
  );
}
