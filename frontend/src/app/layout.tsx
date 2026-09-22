import { Inter } from 'next/font/google';
import '@/styles/globals.css';

const geist = Inter({ subsets: ['latin'], variable: '--font-sans' });

export const metadata = {
  title: 'Narrative Sniper',
  description: 'Real-time narrative detection and trading dashboard',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${geist.variable} antialiased`}>
      <body className="min-h-screen bg-background font-sans">{children}</body>
    </html>
  );
}