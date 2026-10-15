import type { Metadata, Viewport } from "next";
// Шрифты собираются в бандл (self-hosted): без запросов к Google, кириллица + казахские буквы.
import "@fontsource/golos-text/400.css";
import "@fontsource/golos-text/500.css";
import "@fontsource/golos-text/600.css";
import "@fontsource/unbounded/500.css";
import "@fontsource/unbounded/600.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Umay GPT — ИИ-консультант Umay",
  description: "Подбор товаров Umay по описанию, фото и голосу: бюджет, сравнение, корзина, рассрочка 0-0-24.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#F3F7F7" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
