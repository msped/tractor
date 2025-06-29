import Header from "@/components/Header";
import Footer from "@/components/Footer";
import Box from "@mui/material/Box";
import { SessionProvider } from "next-auth/react";

export default function RootLayout({ children }) {

    return (
        <SessionProvider>
            <Header/>
            <Box sx={{ minHeight: '90vh' }}>
                {children}
            </Box>
            <Footer />
        </SessionProvider>
    );
}
