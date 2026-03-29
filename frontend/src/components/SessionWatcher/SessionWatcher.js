"use client";
import { useEffect } from "react";
import { useSession, signOut as realSignOut } from "next-auth/react";
import { useRouter } from "next/navigation";

const CHECK_INTERVAL = 5 * 60 * 1000;

export function SessionWatcher({ signOut = realSignOut, checkInterval = CHECK_INTERVAL }) {
    const { data: session, status, update } = useSession();
    const router = useRouter();

    useEffect(() => {
        const interval = setInterval(update, checkInterval);
        return () => clearInterval(interval);
    }, [update, checkInterval]);

    useEffect(() => {
        if (status === "unauthenticated" || session?.error === "RefreshTokenError") {
            signOut({ redirect: false }).then(() => {
                router.push("/?error=SessionExpired");
            });
        }
    }, [session?.error, status, router, signOut]);

    return null;
}
