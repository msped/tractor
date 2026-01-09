'use client';

import { Box } from '@mui/material';
import { NavSidebar } from '@/components/NavSidebar';
import { SidebarProvider, useSidebar } from '@/contexts/SidebarContext';

function DashboardContent({ children }) {
    const { width } = useSidebar();

    return (
        <Box sx={{ display: 'flex', minHeight: '100vh' }}>
            <NavSidebar />
            <Box
                component="main"
                sx={{
                    flexGrow: 1,
                    ml: `${width}px`,
                    bgcolor: 'grey.50',
                    minHeight: '100vh',
                    width: `calc(100% - ${width}px)`,
                    maxWidth: `calc(100% - ${width}px)`,
                    overflow: 'hidden',
                    transition: 'margin-left 0.2s ease-in-out, width 0.2s ease-in-out, max-width 0.2s ease-in-out',
                }}
            >
                {children}
            </Box>
        </Box>
    );
}

export default function DashboardLayout({ children }) {
    return (
        <SidebarProvider>
            <DashboardContent>{children}</DashboardContent>
        </SidebarProvider>
    );
}
