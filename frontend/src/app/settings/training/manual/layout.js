import React from 'react'
import { Container, Box } from '@mui/material'

export default function Layout({ children }) {
    return (
        <Container maxWidth="lg" sx={{ mt: 4 }}>
            <Box>
                {children}
            </Box>
        </Container>
    )
}
