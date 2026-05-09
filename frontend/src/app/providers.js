'use client';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { SWRConfig } from 'swr';
import toast from 'react-hot-toast';
import { createAppTheme } from '@/theme';
import { ColorModeProvider, useColorMode } from '@/contexts/ColorModeContext';
import { SessionProvider } from '@/contexts/SessionContext';

const swrConfig = { onError: () => toast.error('Failed to load data. Please refresh the page.') };

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
        <ColorModeProvider>
            <AppRouterCacheProvider>
                <ThemeWrapper>
                    <SWRConfig value={swrConfig}>
                        <SessionProvider>
                            {children}
                        </SessionProvider>
                    </SWRConfig>
                </ThemeWrapper>
            </AppRouterCacheProvider>
        </ColorModeProvider>
    );
}
