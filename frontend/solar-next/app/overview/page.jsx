import {redirect} from "next/navigation";
export default async function OverviewRoute({searchParams}) {
  redirect((await searchParams).demo === "1" ? "/?demo=1" : "/");
}
