import { redirect } from "next/navigation";
import { auth } from "@/auth"
import LoginComponent from "@/components/LoginComponent";

export default async function Home() {
  const session = await auth();

  if (session) {
      redirect("/dashboard");
    return null;
  }

  return <LoginComponent />;
}
