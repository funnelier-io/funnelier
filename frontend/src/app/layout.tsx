import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "فانلیر — تحلیل فانل بازاریابی",
  description: "پلتفرم تحلیل فانل بازاریابی و بهینه‌سازی نرخ تبدیل",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fa" dir="rtl">
      <body className="antialiased">{children}</body>
    </html>
  );
}
