import React from 'react'
import { Box, Typography } from '@mui/material';

export default function Footer() {
    return (
        <Box
            component="footer"
            sx={{
                width: '100%',
                py: 2,
                px: 2,
                backgroundColor: 'background.paper',
                textAlign: 'center',
            }}
        >
            <Typography variant="body2" color="text.secondary">
                &copy; {new Date().getFullYear()} Redactor. All rights reserved.
            </Typography>
        </Box>
    )
}
