import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import { Roboto } from 'next/font/google';
import { ThemeProvider } from '@mui/material/styles';
import { Toaster } from 'react-hot-toast';
import theme from '../theme';
import "./globals.css";
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { SessionProvider } from "next-auth/react";

const roboto = Roboto({
  weight: ['300', '400', '500', '700'],
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-roboto',
});

export default async function RootLayout({ children }) {

  return (
    <html lang="en" className={roboto.variable}>
      <body>
        <SessionProvider>
        <AppRouterCacheProvider>
          <ThemeProvider theme={theme}>
          <Header />
          {children}
          <Footer />
          <Toaster/>
          </ThemeProvider>
        </AppRouterCacheProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
