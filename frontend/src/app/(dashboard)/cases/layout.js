import Box from "@mui/material/Box";

export default function RootLayout({ children }) {

    return (
        <Box sx={{ minHeight: '90vh' }}>
            {children}
        </Box>
    );
}
