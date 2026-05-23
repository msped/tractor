import { auth } from '@/auth';
import { headers } from 'next/headers';
import { NextResponse } from 'next/server';

export async function GET() {
    try {
        await auth.api.signOut({ headers: await headers() });
    } catch {
        // Session may already be invalid — proceed to redirect regardless
    }
    return NextResponse.redirect(new URL('/', process.env.BETTER_AUTH_URL || 'http://localhost:3000'));
}
