import { Roboto } from 'next/font/google';
import { Toaster } from 'react-hot-toast';
import "./globals.css";
import { Footer } from '@/components/Footer';
import Providers from '@/app/providers'

const roboto = Roboto({
  weight: ['300', '400', '500', '700'],
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-roboto',
});

export const metadata = {
  other: {
    'apple-mobile-web-app-title': 'Tractor',
  },
};

export default async function RootLayout({ children }) {

  return (
    <html lang="en" className={roboto.variable}>
      <body>
        <Providers>
            {children}
          <Footer />
          <Toaster/>
        </Providers>
      </body>
    </html>
  );
}
