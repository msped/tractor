'use client';
import { createTheme } from '@mui/material/styles';

const theme = createTheme({
    typography: {
        fontFamily: 'var(--font-roboto)',
    },
    palette: {
        warning: {
            main: '#b55401',
            contrastText: '#fff',
        }
    }
});

export default theme;
