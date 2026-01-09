import Box from "@mui/material/Box";

export default function RootLayout({ children }) {

    return (
        <Box mt={2}>
            {children}
        </Box>
    );
}
