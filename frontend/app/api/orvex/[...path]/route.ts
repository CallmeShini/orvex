import { NextRequest } from "next/server";

export const runtime = "nodejs";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

const API_BASE_URL = process.env.ORVEX_API_URL ?? "http://127.0.0.1:8000";

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const upstreamUrl = `${API_BASE_URL.replace(/\/$/, "")}/${path.join("/")}${request.nextUrl.search}`;
  const requestHeaders = new Headers(request.headers);

  requestHeaders.delete("host");
  requestHeaders.delete("connection");
  requestHeaders.delete("content-length");
  requestHeaders.delete("accept-encoding");

  try {
    const hasBody = request.method !== "GET" && request.method !== "HEAD";
    const response = await fetch(upstreamUrl, {
      method: request.method,
      headers: requestHeaders,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store"
    });

    const responseHeaders = new Headers(response.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("transfer-encoding");

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders
    });
  } catch (error) {
    return Response.json(
      {
        detail: error instanceof Error ? error.message : "Could not reach Orvex API."
      },
      { status: 502 }
    );
  }
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}
