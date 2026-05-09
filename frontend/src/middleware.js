import { NextResponse } from "next/server"
import { auth } from "@/auth"

export default async function middleware(request) {
    const { nextUrl } = request
    const isLoginPage = nextUrl.pathname === "/"

    const session = await auth.api.getSession({ headers: request.headers })
    const isLoggedIn = !!session

    if (!isLoggedIn && isLoginPage) {
        return NextResponse.next()
    }

    if (!isLoggedIn) {
        const loginUrl = new URL("/", nextUrl.origin)
        return NextResponse.redirect(loginUrl)
    }

    if (isLoggedIn && isLoginPage) {
        return NextResponse.redirect(new URL("/cases", nextUrl.origin))
    }

    return NextResponse.next()
}

export const config = {
    matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
}
