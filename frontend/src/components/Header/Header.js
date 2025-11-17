"use client"

import React from 'react';
import { signOut, useSession } from "next-auth/react";
import { AppBar, Toolbar, Typography, Button, Box, IconButton } from '@mui/material';
import Link from 'next/link';
import SettingsIcon from '@mui/icons-material/Settings';

export const Header = () => {
    const { data: session } = useSession();
    const handleSignOut = async () => {
        await signOut({ callbackUrl: "/" });
    };

    return (
        <AppBar position="static" color="primary">
            <Toolbar>
                <Typography
                    variant="h6"
                    component={Link}
                    href="/"
                    sx={{ color: 'inherit', textDecoration: 'none' }}
                >
                    SAM
                </Typography>

                {session && (
                    <Button color="inherit" component={Link} href="/cases" sx={{ ml: 2 }}>
                        Cases
                    </Button>
                )}

                <Box sx={{ flexGrow: 1 }}></Box>

                {session ? (
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Typography variant="body1" component="div" sx={{ mx: 2 }}>
                            {session.user.username}
                        </Typography>
                        <IconButton
                            color="inherit"
                            component={Link}
                            href="/settings"
                            sx={{ mr: 2 }}
                        >
                            <SettingsIcon />
                        </IconButton>
                        <Button color="inherit" onClick={handleSignOut}>
                            Sign Out
                        </Button>
                    </Box>
                ) : (
                    <Button color="inherit" component={Link} href="/api/auth/signin">
                        Sign In
                    </Button>
                )}
            </Toolbar>
        </AppBar>
    );
};
