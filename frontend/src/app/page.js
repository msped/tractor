import { redirect } from "next/navigation";
import { auth } from "../auth"
import LoginComponent from "@/components/LoginComponent";

export default function Home() {
  const session = auth();

  if (session) {
    redirect("/dashboard");
  }

  return <LoginComponent />;
}
