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

	const pythonRes = await fetch("http://localhost:8000/chat", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ prompt }),
	});

	return new Response(pythonRes.body, {
		headers: { "Content-Type": "text/plain; charset=utf-8" },
	});
}
