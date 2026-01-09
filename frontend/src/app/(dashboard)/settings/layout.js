import Box from "@mui/material/Box";
import Container from "@mui/material/Container";

export default function RootLayout({ children }) {

    return (
        <Container sx={{ mt: 4 }} maxWidth="lg">
            <Box sx={{ minHeight: '90vh' }}>
                {children}
            </Box>
        </Container>
    );
}