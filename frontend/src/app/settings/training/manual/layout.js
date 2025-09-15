import React from 'react'
import { Button, Box, Container } from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

export default function layout({ children }) {
    return (
        <Container sx={{ mt: 4 }}>
            <Button
                href="/admin/training" 
                variant="contained"
                startIcon={<ArrowBackIcon />}
                sx={{ mt: 2 }}
            >
                Back to Training Overview
            </Button>
            <Box>
                {children}
            </Box>
        </Container>
    )
}
