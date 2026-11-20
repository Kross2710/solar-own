import {read} from "../../../shared/read";
import {publicReading} from "../../../overview/telemetry";

export async function GET() {
  const data = publicReading(await read("metrics"));
  return Response.json(data, {status:data ? 200 : 503, headers:{"Cache-Control":"no-store"}});
}
