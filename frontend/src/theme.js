'use client';
import { createTheme } from '@mui/material/styles';

const theme = createTheme({
    typography: {
        fontFamily: 'var(--font-roboto)',
        h1: {
            fontWeight: 700,
            letterSpacing: '-0.02em',
        },
        h2: {
            fontWeight: 600,
            letterSpacing: '-0.01em',
        },
        h3: {
            fontWeight: 600,
        },
        h4: {
            fontWeight: 600,
        },
    },
    palette: {
        primary: {
            main: '#0A2540',  // Deep navy - professional and trustworthy
            light: '#425466',
            dark: '#000000',
            contrastText: '#fff',
        },
        secondary: {
            main: '#635BFF',  // Vibrant purple accent
            light: '#7A73FF',
            dark: '#4B44CC',
            contrastText: '#fff',
        },
        success: {
            main: '#00D4AA',
            contrastText: '#0A2540',
        },
        warning: {
            main: '#FF9500',
            contrastText: '#fff',
        },
        error: {
            main: '#FF5A5A',
            contrastText: '#fff',
        },
        background: {
            default: '#FFFFFF',
            paper: '#FFFFFF',
        },
        text: {
            primary: '#0A2540',
            secondary: '#425466',
        },
        divider: '#E6E8EB',
    },
    shape: {
        borderRadius: 8,
    },
    components: {
        MuiButton: {
            styleOverrides: {
                root: {
                    textTransform: 'none',
                    fontWeight: 600,
                    borderRadius: 8,
                    padding: '10px 20px',
                },
                contained: {
                    boxShadow: 'none',
                    '&:hover': {
                        boxShadow: 'none',
                    },
                },
            },
        },
        MuiCard: {
            styleOverrides: {
                root: {
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
                    border: '1px solid #E6E8EB',
                },
            },
        },
        MuiAppBar: {
            styleOverrides: {
                root: {
                    boxShadow: '0 1px 0 rgba(0, 0, 0, 0.08)',
                },
            },
        },
    },
});

export default theme;
