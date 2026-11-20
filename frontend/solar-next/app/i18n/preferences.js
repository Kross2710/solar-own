import {cookies} from "next/headers";
export async function preferences() {
  const jar = await cookies();
  return {lang:jar.get("solar-lang")?.value === "vi" ? "vi" : "en",
    advanced:jar.get("solar-advanced")?.value === "1"};
}
