import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BiliDigest - B站视频知识资产系统",
  description: "输入B站视频URL，自动提取知识资产，支持图文总结、小红书图文等多种输出",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="h-full">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,500&family=DM+Sans:wght@300;400;500&family=Noto+Sans+SC:wght@300;400;500&display=swap" rel="stylesheet" />
      </head>
      <body className="h-full">{children}</body>
    </html>
  );
}
