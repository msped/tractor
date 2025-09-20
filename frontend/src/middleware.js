import { NextResponse } from "next/server"
import { auth } from "@/auth"

export default auth((req) => {
    const { nextUrl, auth: session } = req

    const isLoggedIn = !!session
    const isLoginPage = nextUrl.pathname === "/"

    if (!isLoggedIn && isLoginPage) {
        return NextResponse.next()
    }

    // If trying to access /<> while not logged in
    if (!isLoggedIn) {
        const loginUrl = new URL("/", nextUrl.origin)
        return NextResponse.redirect(loginUrl)
    }

    // If trying to access / while already logged in
    if (isLoggedIn && isLoginPage) {
        return NextResponse.redirect(new URL("/cases", nextUrl.origin))
    }

    return NextResponse.next()
})

export const config = {
    // Match all paths except for static files and API routes
    matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
};