import { LoginComponent } from "@/components/LoginComponent";

export default async function Home({ searchParams }) {
  const params = await searchParams;
  const socialProviders = process.env.BETTER_AUTH_MICROSOFT_CLIENT_ID
    ? [{ id: "microsoft", name: "Microsoft" }]
    : [];
  return <LoginComponent sessionError={params?.error} socialProviders={socialProviders} />;
}
