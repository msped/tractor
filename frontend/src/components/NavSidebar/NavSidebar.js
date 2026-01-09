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
    Avatar,
} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import PsychologyIcon from '@mui/icons-material/Psychology';
import SettingsIcon from '@mui/icons-material/Settings';
import AddIcon from '@mui/icons-material/Add';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import LogoutIcon from '@mui/icons-material/Logout';
import { useSession, signOut } from 'next-auth/react';
import { useSidebar, SIDEBAR_WIDTH_EXPANDED, SIDEBAR_WIDTH_COLLAPSED } from '@/contexts/SidebarContext';

export { SIDEBAR_WIDTH_EXPANDED as SIDEBAR_WIDTH };

export function NavSidebar() {
    const pathname = usePathname();
    const { collapsed, toggle, width } = useSidebar();
    const { data: session } = useSession();

    const handleLogout = () => signOut({ callbackUrl: '/' });

    // Get user initials for avatar fallback
    const getUserInitials = (name) => {
        if (!name) return '?';
        const names = name.split(' ');
        if (names.length >= 2) {
            return `${names[0][0]}${names[names.length - 1][0]}`.toUpperCase();
        }
        return name[0].toUpperCase();
    };

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

                {/* User Profile & Logout */}
                {session?.user && (
                    <Box
                        sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: 1,
                            py: 1,
                        }}
                    >
                        {collapsed ? (
                            <>
                                <Tooltip title={session.user.name || session.user.email || 'User'} placement="right">
                                    <Avatar
                                        src={session.user.image}
                                        alt={session.user.name || 'User'}
                                        sx={{
                                            width: 36,
                                            height: 36,
                                            bgcolor: 'primary.main',
                                            fontSize: '0.875rem',
                                        }}
                                    >
                                        {getUserInitials(session.user.name)}
                                    </Avatar>
                                </Tooltip>
                                <Tooltip title="Logout" placement="right">
                                    <IconButton
                                        onClick={handleLogout}
                                        size="small"
                                        sx={{
                                            color: 'text.secondary',
                                            '&:hover': {
                                                color: 'error.main',
                                                bgcolor: 'error.lighter',
                                            },
                                        }}
                                    >
                                        <LogoutIcon fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                            </>
                        ) : (
                            <Box
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    width: '100%',
                                    px: 1,
                                    py: 0.5,
                                    borderRadius: 1,
                                }}
                            >
                                <Avatar
                                    src={session.user.image}
                                    alt={session.user.name || 'User'}
                                    sx={{
                                        width: 36,
                                        height: 36,
                                        bgcolor: 'primary.main',
                                        fontSize: '0.875rem',
                                    }}
                                >
                                    {getUserInitials(session.user.name)}
                                </Avatar>
                                <Box sx={{ ml: 1.5, flexGrow: 1, minWidth: 0 }}>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            fontWeight: 500,
                                            whiteSpace: 'nowrap',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                        }}
                                    >
                                        {session.user.name || 'User'}
                                    </Typography>
                                    {session.user.email && (
                                        <Typography
                                            variant="caption"
                                            color="text.secondary"
                                            sx={{
                                                whiteSpace: 'nowrap',
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                display: 'block',
                                            }}
                                        >
                                            {session.user.email}
                                        </Typography>
                                    )}
                                </Box>
                                <Tooltip title="Logout">
                                    <IconButton
                                        onClick={handleLogout}
                                        size="small"
                                        sx={{
                                            color: 'text.secondary',
                                            '&:hover': {
                                                color: 'error.main',
                                                bgcolor: 'action.hover',
                                            },
                                        }}
                                    >
                                        <LogoutIcon fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                            </Box>
                        )}
                    </Box>
                )}
            </Box>
        </Box>
    );
}
