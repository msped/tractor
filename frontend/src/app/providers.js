import React from 'react'
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import { ThemeProvider } from '@mui/material/styles';
import { SessionProvider } from "next-auth/react";
import theme from '@/theme';

export default function Providers({ children}) {
    return (
        <SessionProvider>
                <AppRouterCacheProvider>
                    <ThemeProvider theme={theme}>
                        {children}
                    </ThemeProvider>
                </AppRouterCacheProvider>
        </SessionProvider>
    )
}
