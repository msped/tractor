'use client';
import { createContext, useContext, useEffect, useMemo } from 'react';
import { authClient } from '@/lib/auth-client';
import { setClientToken } from '@/api/apiClient';

export const SessionContext = createContext(undefined);

export function SessionProvider({ children }) {
    const { data: session, isPending } = authClient.useSession();

    useEffect(() => {
        setClientToken(session?.user?.access_token ?? null);
    }, [session?.user?.access_token]);

    const value = useMemo(() => ({ session, isPending }), [session, isPending]);

    return (
        <SessionContext.Provider value={value}>
            {children}
        </SessionContext.Provider>
    );
}

export function useSession() {
    const ctx = useContext(SessionContext);
    if (ctx === undefined) {
        throw new Error('useSession must be used within a SessionProvider');
    }
    return ctx;
}
