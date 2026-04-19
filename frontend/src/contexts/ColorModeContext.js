'use client';
import { createContext, useContext, useState, useEffect } from 'react';

const ColorModeContext = createContext({ mode: 'light', toggleColorMode: () => {} });

export const useColorMode = () => useContext(ColorModeContext);

export function ColorModeProvider({ children }) {
    const [mode, setMode] = useState('light');

    useEffect(() => {
        const stored = localStorage.getItem('colorMode');
        if (stored === 'dark') setMode('dark');
    }, []);

    const toggleColorMode = () => {
        setMode(prev => {
            const next = prev === 'light' ? 'dark' : 'light';
            localStorage.setItem('colorMode', next);
            return next;
        });
    };

    return (
        <ColorModeContext.Provider value={{ mode, toggleColorMode }}>
            {children}
        </ColorModeContext.Provider>
    );
}
