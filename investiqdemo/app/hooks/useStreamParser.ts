// Strongly-typed shapes that match the backend NDJSON protocol
export interface ThinkingChunk {
    type: "thinking_content";
    data: string;
}

export interface ResponseChunk {
    type: "response_content";
    data: string;
}

export interface DisplayModule {
    type: "LineGraph" | "BarGraph" | "ScatterPlot";
    data: Record<string, unknown>;
}

export interface DisplayChunk {
    type: "display_modules";
    data: DisplayModule[];
}

export type StreamChunk = ThinkingChunk | ResponseChunk | DisplayChunk;

export interface StreamHandlers {
    onThinking: (text: string) => void;
    onResponse: (text: string) => void;
    onDisplay: (modules: DisplayModule[]) => void;
}

/**
 * Parses a streaming NDJSON response from the backend and dispatches
 * each chunk to the appropriate handler. Handles incomplete lines across
 * chunk boundaries via an internal line buffer.
 */
export async function parseStream(
    response: Response,
    handlers: StreamHandlers
): Promise<void> {
    if (!response.body) {
        throw new Error("Response body is null");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let lineBuffer = "";

    const dispatch = (parsed: StreamChunk) => {
        if (parsed.type === "thinking_content") {
            handlers.onThinking(parsed.data);
        } else if (parsed.type === "response_content") {
            handlers.onResponse(parsed.data);
        } else if (parsed.type === "display_modules") {
            handlers.onDisplay(parsed.data);
        }
    };

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        lineBuffer += decoder.decode(value, { stream: true });
        const lines = lineBuffer.split("\n");
        // Last element may be incomplete — keep it for the next read
        lineBuffer = lines.pop() ?? "";

        for (const line of lines) {
            if (!line.trim()) continue;
            try {
                const parsed = JSON.parse(line) as StreamChunk;
                dispatch(parsed);
            } catch {
                console.warn("[useStreamParser] Failed to parse chunk:", line);
            }
        }
    }

    // Flush any remaining buffered content
    if (lineBuffer.trim()) {
        try {
            const parsed = JSON.parse(lineBuffer) as StreamChunk;
            dispatch(parsed);
        } catch {
            console.warn("[useStreamParser] Leftover unparseable buffer:", lineBuffer);
        }
    }
}
