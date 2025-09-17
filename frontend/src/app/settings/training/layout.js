"use client"

import React from 'react'
import { useRouter } from 'next/navigation';
import { Button, Box, Container } from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

export default function Layout({ children }) {
    const router = useRouter();
    const handleBackButton = () => {
        router.back();
    }
    
    return (
        <Container maxWidth="lg" sx={{ m: 4 }}>
            <Button
                onClick={handleBackButton}
                variant="contained"
                startIcon={<ArrowBackIcon />}
                sx={{ mt: 2 }}
            >
                Back
            </Button>
            <Box>
                {children}
            </Box>
        </Container>
    )
}
