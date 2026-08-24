export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json({ pong: true, ts: new Date().toISOString() });
}
