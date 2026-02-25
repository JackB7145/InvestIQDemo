export async function GET() {
    const apiUrl = process.env.PYTHON_API_URL ?? "http://localhost:8000";
    try {
        const res = await fetch(`${apiUrl}/health`, {
            // Short timeout — we only need to know if the service is up
            signal: AbortSignal.timeout(3000),
        });
        if (res.ok) {
            return new Response(JSON.stringify({ status: "online" }), {
                headers: { "Content-Type": "application/json" },
            });
        }
        return new Response(JSON.stringify({ status: "offline" }), {
            status: 502,
            headers: { "Content-Type": "application/json" },
        });
    } catch {
        return new Response(JSON.stringify({ status: "offline" }), {
            status: 503,
            headers: { "Content-Type": "application/json" },
        });
    }
}
