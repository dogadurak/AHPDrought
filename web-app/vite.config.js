import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages proje sitesi `/<repo>/` altında sunulur, yerel geliştirme ise
// kökten. Yol, dağıtım iş akışının verdiği BASE_PATH ile belirlenir; tüm
// varlık referansları koda gömülü mutlak yollar yerine
// `import.meta.env.BASE_URL` üzerinden çözülür.
export default defineConfig({
  base: process.env.BASE_PATH ?? "/",
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
