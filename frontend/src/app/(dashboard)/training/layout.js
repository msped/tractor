"use client"

import React from 'react'
import { useRouter, usePathname } from 'next/navigation';
import { Button, Box, Container } from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

export default function Layout({ children }) {
    const router = useRouter();
    const pathname = usePathname();

    const handleBackButton = () => {
        router.back();
    }

    const showBackButton = pathname !== '/training';
    
    return (
        <Container maxWidth="lg" sx={{ m: 4 }}>
            {showBackButton &&<Button
                onClick={handleBackButton}
                variant="contained"
                startIcon={<ArrowBackIcon />}
                sx={{ mt: 2 }}
            >
                Back
            </Button>}
            <Box>
                {children}
            </Box>
        </Container>
    )
}
