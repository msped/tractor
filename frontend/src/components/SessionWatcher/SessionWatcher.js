"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/contexts/SessionContext";

export function SessionWatcher() {
    const router = useRouter();
    const { session, isPending } = useSession();

    useEffect(() => {
        if (!isPending && !session) router.push("/");
    }, [session, isPending, router]);

    return null;
}
