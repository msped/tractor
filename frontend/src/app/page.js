import { LoginComponent } from "@/components/LoginComponent";

export default async function Home({ searchParams }) {
  const params = await searchParams;
  return <LoginComponent sessionError={params?.error} />;
}
