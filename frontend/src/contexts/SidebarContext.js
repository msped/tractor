'use client';

import { createContext, useContext, useState } from 'react';

const SidebarContext = createContext(undefined);

export const SIDEBAR_WIDTH_EXPANDED = 260;
export const SIDEBAR_WIDTH_COLLAPSED = 72;

export function SidebarProvider({ children }) {
    const [collapsed, setCollapsed] = useState(false);

    const toggle = () => setCollapsed(prev => !prev);

    const width = collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED;

    return (
        <SidebarContext.Provider value={{ collapsed, toggle, width }}>
            {children}
        </SidebarContext.Provider>
    );
}

export function useSidebar() {
    const context = useContext(SidebarContext);
    if (context === undefined) {
        throw new Error('useSidebar must be used within a SidebarProvider');
    }
    return context;
}
