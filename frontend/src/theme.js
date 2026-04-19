'use client';
import { createTheme } from '@mui/material/styles';

export function createAppTheme(mode = 'light') {
    return createTheme({
        typography: {
            fontFamily: 'var(--font-roboto)',
            h1: { fontWeight: 700, letterSpacing: '-0.02em' },
            h2: { fontWeight: 600, letterSpacing: '-0.01em' },
            h3: { fontWeight: 500 },
            h4: { fontWeight: 500 },
        },
        palette: {
            mode,
            primary: {
                main: mode === 'dark' ? '#2D6A9F' : '#0A2540',
                light: mode === 'dark' ? '#5B8CB7' : '#425466',
                dark: mode === 'dark' ? '#1A4F7A' : '#000000',
                contrastText: '#fff',
            },
            secondary: {
                main: '#635BFF',
                light: '#7A73FF',
                dark: '#4B44CC',
                contrastText: '#fff',
            },
            info: { main: '#0288d1', light: '#03a9f4', dark: '#01579b', contrastText: '#fff' },
            success: { main: '#2e7d32', light: '#4caf50', dark: '#1b5e20', contrastText: '#fff' },
            warning: { main: '#ed6c02', light: '#ff9800', dark: '#e65100', contrastText: '#fff' },
            error: { main: '#d32f2f', light: '#ef5350', dark: '#c62828', contrastText: '#fff' },
        },
        shape: { borderRadius: 8 },
        components: {
            MuiButton: {
                styleOverrides: {
                    root: {
                        textTransform: 'none',
                        fontWeight: 600,
                        borderRadius: 8,
                    },
                    contained: {
                        boxShadow: 'none',
                        '&:hover': { boxShadow: 'none' },
                    },
                },
            },
            MuiCard: {
                styleOverrides: {
                    root: ({ theme }) => ({
                        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
                        border: `1px solid ${theme.palette.divider}`,
                    }),
                },
            },
        },
    });
}

export default createAppTheme('light');
