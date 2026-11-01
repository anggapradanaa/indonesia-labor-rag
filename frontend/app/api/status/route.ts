import { getBackendStatus } from "@/lib/space";

export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(await getBackendStatus());
}
