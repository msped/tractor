'use client';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { SessionProvider } from "next-auth/react";
import { createAppTheme } from '@/theme';
import { ColorModeProvider, useColorMode } from '@/contexts/ColorModeContext';

function ThemeWrapper({ children }) {
    const { mode } = useColorMode();
    const theme = createAppTheme(mode);
    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            {children}
        </ThemeProvider>
    );
}

export default function Providers({ children }) {
    return (
        <SessionProvider>
            <ColorModeProvider>
                <AppRouterCacheProvider>
                    <ThemeWrapper>
                        {children}
                    </ThemeWrapper>
                </AppRouterCacheProvider>
            </ColorModeProvider>
        </SessionProvider>
    );
}
