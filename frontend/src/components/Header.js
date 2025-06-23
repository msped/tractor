"use client"

import React from 'react';
import { signOut, useSession } from "next-auth/react";
import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material';
import Link from 'next/link';

export default function Header() {
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
                    Redactor
                </Typography>

                {session && (
                    <Button color="inherit" component={Link} href="/cases" sx={{ ml: 2 }}>
                        My Cases
                    </Button>
                )}

                <Box sx={{ flexGrow: 1 }}></Box>

                {session ? (
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Button color="inherit" component={Link} href="/cases/new">
                            New Case
                        </Button>
                        <Typography variant="body1" component="div" sx={{ mx: 2 }}>
                            {session.user.username}
                        </Typography>
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
}
