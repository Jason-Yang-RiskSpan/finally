import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'FinAlly - AI Trading Workstation',
  description: 'Finance Ally - your AI-powered trading workstation',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-bg-base text-slate-200 font-mono antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}
