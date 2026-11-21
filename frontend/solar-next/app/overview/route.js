import {redirect} from "next/navigation";

export function GET(request) {
  const demo = request.nextUrl.searchParams.getAll("demo");
  redirect(demo.length === 1 && demo[0] === "1" ? "/?demo=1" : "/");
}
