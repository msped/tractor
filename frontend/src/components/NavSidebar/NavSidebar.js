'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
    Box,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Divider,
    Typography,
    IconButton,
    Tooltip,
} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import PsychologyIcon from '@mui/icons-material/Psychology';
import SettingsIcon from '@mui/icons-material/Settings';
import AddIcon from '@mui/icons-material/Add';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useSidebar, SIDEBAR_WIDTH_EXPANDED, SIDEBAR_WIDTH_COLLAPSED } from '@/contexts/SidebarContext';

export { SIDEBAR_WIDTH_EXPANDED as SIDEBAR_WIDTH };

export function NavSidebar() {
    const pathname = usePathname();
    const { collapsed, toggle, width } = useSidebar();

    // Show team UI only for org plans when user has multiple teams or is an admin

    // Base nav items
    const allNavItems = [
        { label: 'Cases', href: '/cases', icon: <FolderIcon /> },
        { label: 'Training', href: '/training', icon: <PsychologyIcon /> },
    ];

    // Filter nav items based on visibility conditions
    const navItems = allNavItems.filter(item =>
        item.showWhen === undefined ? true : item.showWhen
    );

    return (
        <Box
            component="nav"
            sx={{
                width: width,
                flexShrink: 0,
                borderRight: '1px solid',
                borderColor: 'divider',
                height: '100vh',
                position: 'fixed',
                top: 0,
                left: 0,
                bgcolor: 'background.paper',
                display: 'flex',
                flexDirection: 'column',
                zIndex: 1200,
                transition: 'width 0.2s ease-in-out',
                overflow: 'hidden',
            }}
        >
            {/* Logo & Collapse Toggle */}
            <Box sx={{
                p: collapsed ? 1.5 : 2.5,
                borderBottom: '1px solid',
                borderColor: 'divider',
                display: 'flex',
                alignItems: 'center',
                justifyContent: collapsed ? 'center' : 'space-between',
                minHeight: 64,
            }}>
                {!collapsed && (
                    <Typography
                        variant="h6"
                        component={Link}
                        href="/cases"
                        sx={{
                            textDecoration: 'none',
                            color: 'primary.main',
                            fontWeight: 700,
                            fontSize: '1.25rem',
                        }}
                    >
                        Tractor
                    </Typography>
                )}
                <IconButton
                    onClick={toggle}
                    size="small"
                    sx={{
                        color: 'text.secondary',
                        '&:hover': { bgcolor: 'action.hover' }
                    }}
                >
                    {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
                </IconButton>
            </Box>

            {/* New Case Button */}
            <Box sx={{ px: collapsed ? 1 : 2, py: 2 }}>
                <Tooltip title={collapsed ? 'New Case' : ''} placement="right">
                    <ListItemButton
                        component={Link}
                        href="/cases/new"
                        sx={{
                            borderRadius: 1,
                            bgcolor: 'secondary.main',
                            color: 'white',
                            justifyContent: collapsed ? 'center' : 'flex-start',
                            px: collapsed ? 1.5 : 2,
                            '&:hover': {
                                bgcolor: 'secondary.dark',
                            },
                        }}
                    >
                        <ListItemIcon sx={{ minWidth: collapsed ? 0 : 36, color: 'inherit' }}>
                            <AddIcon />
                        </ListItemIcon>
                        {!collapsed && (
                            <ListItemText
                                primary="New Case"
                                sx={{ fontWeight: 600 }}
                            />
                        )}
                    </ListItemButton>
                </Tooltip>
            </Box>

            {/* Nav Items */}
            <List sx={{ flexGrow: 1, px: collapsed ? 1 : 1.5, py: 1 }}>
                {navItems.map((item) => {
                    const isActive = pathname === item.href ||
                        (item.href !== '/' && pathname.startsWith(item.href));

                    return (
                        <ListItem key={item.href} disablePadding sx={{ mb: 0.5 }}>
                            <Tooltip title={collapsed ? item.label : ''} placement="right">
                                <ListItemButton
                                    component={Link}
                                    href={item.href}
                                    selected={isActive}
                                    sx={{
                                        borderRadius: 1,
                                        justifyContent: collapsed ? 'center' : 'flex-start',
                                        px: collapsed ? 1.5 : 2,
                                        '&.Mui-selected': {
                                            bgcolor: 'action.selected',
                                            '&:hover': {
                                                bgcolor: 'action.selected',
                                            },
                                        },
                                    }}
                                >
                                    <ListItemIcon
                                        sx={{
                                            minWidth: collapsed ? 0 : 36,
                                            color: isActive ? 'primary.main' : 'text.secondary',
                                        }}
                                    >
                                        {item.icon}
                                    </ListItemIcon>
                                    {!collapsed && (
                                        <ListItemText
                                            primary={item.label}
                                            sx={{
                                                fontWeight: isActive ? 600 : 400,
                                                color: isActive ? 'primary.main' : 'text.primary',
                                            }}
                                        />
                                    )}
                                </ListItemButton>
                            </Tooltip>
                        </ListItem>
                    );
                })}
            </List>

            <Divider />

            {/* Settings & User */}
            <Box sx={{ p: collapsed ? 1 : 1.5 }}>
                <Tooltip title={collapsed ? 'Settings' : ''} placement="right">
                    <ListItemButton
                        component={Link}
                        href="/settings"
                        selected={pathname === '/settings'}
                        sx={{
                            borderRadius: 1,
                            mb: 1.5,
                            justifyContent: collapsed ? 'center' : 'flex-start',
                            px: collapsed ? 1.5 : 2,
                            '&.Mui-selected': {
                                bgcolor: 'action.selected',
                            },
                        }}
                    >
                        <ListItemIcon sx={{ minWidth: collapsed ? 0 : 36, color: 'text.secondary' }}>
                            <SettingsIcon />
                        </ListItemIcon>
                        {!collapsed && <ListItemText primary="Settings" />}
                    </ListItemButton>
                </Tooltip>

                <Box sx={{ px: collapsed ? 0 : 1.5, py: 1, display: 'flex', justifyContent: 'center' }}>
                    {/* User */}
                </Box>
            </Box>
        </Box>
    );
}
