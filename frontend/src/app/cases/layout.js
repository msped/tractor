import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { SessionProvider } from "next-auth/react";

export default function RootLayout({ children }) {

    return (
        <SessionProvider>
            <Header/>
            {children}
            <Footer />
        </SessionProvider>
    );
}
