// app/api/chat/route.ts
import { NextRequest } from "next/server";

export async function POST(req: NextRequest) {
	const { prompt } = await req.json();

	if (!prompt?.trim()) {
		return new Response(JSON.stringify({ error: "Prompt is required" }), {
			status: 400,
			headers: { "Content-Type": "application/json" },
		});
	}

	const apiUrl = process.env.PYTHON_API_URL ?? "http://localhost:8000";
	const pythonRes = await fetch(`${apiUrl}/chat`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ prompt }),
	});

	if (!pythonRes.ok) {
		return new Response(
			JSON.stringify({ error: `Upstream error: ${pythonRes.status}` }),
			{ status: 502, headers: { "Content-Type": "application/json" } },
		);
	}

	if (!pythonRes.body) {
		return new Response(
			JSON.stringify({ error: "No response body from upstream" }),
			{ status: 502, headers: { "Content-Type": "application/json" } },
		);
	}

	// Pipe through a TransformStream so Next.js handles backpressure correctly
	const { readable, writable } = new TransformStream();
	pythonRes.body.pipeTo(writable);

	return new Response(readable, {
		headers: {
			"Content-Type": "text/plain; charset=utf-8",
			// Prevent Next.js / nginx from buffering the stream
			"X-Accel-Buffering": "no",
			"Cache-Control": "no-cache",
		},
	});
}
