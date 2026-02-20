"use client";
import { Box } from "@mui/material";
import InputBox from "./components/InputBox";
import GraphBox from "./components/GraphBox";
import { useState } from "react";
import ChatBox from "./components/ChatBox";
import {
	LineGraph,
	BarGraph,
	ScatterPlotGraph,
	ChartData,
} from "./classes/charts";

export interface ChatMessage {
	type: "user" | "bot" | "thinking";
	text: string;
}

// Matches the NDJSON shape from the backend
interface StreamChunk {
	type: "thinking_content" | "response_content" | "display_modules";
	data: string | any[];
}

export default function Home() {
	const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
	const [displayBox, setDisplayBox] = useState<ChartData[]>([]);

	const toolHandlers: Record<string, (data: any) => void> = {
		LineGraph: (data) =>
			setDisplayBox((prev) => [...prev, LineGraph.fromData(data)]),
		BarGraph: (data) =>
			setDisplayBox((prev) => [...prev, BarGraph.fromData(data)]),
		ScatterPlot: (data) =>
			setDisplayBox((prev) => [...prev, ScatterPlotGraph.fromData(data)]),
	};

	const handleSubmit = async (prompt: string) => {
		if (!prompt.trim()) return;

		// Add user message and seed thinking bubble
		setChatMessages((prev) => [
			...prev,
			{ text: prompt, type: "user" },
			{ text: "", type: "thinking" },
		]);

		try {
			const response = await fetch("/api/chat", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ prompt }),
			});

			if (!response.ok)
				throw new Error(`HTTP error! status: ${response.status}`);

			const reader = response.body!.getReader();
			const decoder = new TextDecoder();
			let botSeeded = false;
			// Buffer incomplete lines across chunks
			let lineBuffer = "";

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				// Append decoded bytes to buffer and split on newlines
				lineBuffer += decoder.decode(value, { stream: true });
				const lines = lineBuffer.split("\n");

				// Last element may be incomplete — keep it in the buffer
				lineBuffer = lines.pop() ?? "";

				for (const line of lines) {
					if (!line.trim()) continue;

					let parsed: StreamChunk;
					try {
						parsed = JSON.parse(line);
					} catch {
						console.warn("Failed to parse chunk:", line);
						continue;
					}

					if (parsed.type === "thinking_content") {
						// Append to the thinking bubble
						setChatMessages((prev) => {
							const updated = [...prev];
							updated[updated.length - 1] = {
								...updated[updated.length - 1],
								text:
									updated[updated.length - 1].text + (parsed.data as string),
							};
							return updated;
						});
					} else if (parsed.type === "response_content") {
						// Swap thinking bubble → bot message on first response chunk
						if (!botSeeded) {
							setChatMessages((prev) => {
								const updated = [...prev];
								updated[updated.length - 1] = {
									text: "",
									type: "bot",
								};
								return updated;
							});
							botSeeded = true;
						}
						setChatMessages((prev) => {
							const updated = [...prev];
							updated[updated.length - 1] = {
								...updated[updated.length - 1],
								text:
									updated[updated.length - 1].text + (parsed.data as string),
							};
							return updated;
						});
					} else if (parsed.type === "display_modules") {
						// Render each chart via its handler
						(parsed.data as any[]).forEach(
							(module: { type: string; data: any }) => {
								const handler = toolHandlers[module.type];
								if (handler) handler(module.data);
								else
									console.warn(`No handler for module type: "${module.type}"`);
							},
						);
					}
				}
			}

			// Flush any remaining buffer content
			if (lineBuffer.trim()) {
				try {
					const parsed: StreamChunk = JSON.parse(lineBuffer);
					if (parsed.type === "display_modules") {
						(parsed.data as any[]).forEach(
							(module: { type: string; data: any }) => {
								const handler = toolHandlers[module.type];
								if (handler) handler(module.data);
							},
						);
					}
				} catch {
					console.warn("Leftover unparseable buffer:", lineBuffer);
				}
			}
		} catch (error) {
			console.error("Chat API error:", error);
			setChatMessages((prev) => [
				...prev,
				{ text: "Something went wrong. Please try again.", type: "bot" },
			]);
		}
	};

	return (
		<Box
			sx={{
				height: "100vh",
				width: "100vw",
				display: "flex",
				flexDirection: "column",
				bgcolor: "#f0f4fb",
				overflow: "hidden",
			}}
		>
			{/* Header */}
			<Box
				sx={{
					px: 4,
					py: 1.5,
					bgcolor: "white",
					borderBottom: "1px solid #e3eaf5",
					display: "flex",
					alignItems: "center",
					justifyContent: "space-between",
					boxShadow: "0 1px 4px rgba(25,118,210,0.06)",
					flexShrink: 0,
				}}
			>
				<Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
					<Box
						sx={{
							width: 32,
							height: 32,
							borderRadius: "8px",
							bgcolor: "#1976d2",
							display: "flex",
							alignItems: "center",
							justifyContent: "center",
							boxShadow: "0 2px 8px rgba(25,118,210,0.3)",
						}}
					>
						<svg
							width="16"
							height="16"
							viewBox="0 0 16 16"
							fill="none"
						>
							<path
								d="M3 8h10M8 3v10"
								stroke="white"
								strokeWidth="2"
								strokeLinecap="round"
							/>
						</svg>
					</Box>
					<Box
						component="span"
						sx={{
							fontSize: "1rem",
							fontWeight: 700,
							color: "#1a1a2e",
							letterSpacing: "-0.01em",
						}}
					>
						Analyst
					</Box>
					<Box
						component="span"
						sx={{
							fontSize: "0.65rem",
							fontWeight: 600,
							color: "#1976d2",
							bgcolor: "rgba(25,118,210,0.08)",
							border: "1px solid rgba(25,118,210,0.2)",
							px: 1,
							py: 0.25,
							borderRadius: "4px",
							letterSpacing: "0.08em",
							textTransform: "uppercase",
						}}
					>
						Beta
					</Box>
				</Box>

				<Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
					<Box
						sx={{
							width: 8,
							height: 8,
							borderRadius: "50%",
							bgcolor: "#22c55e",
							boxShadow: "0 0 6px rgba(34,197,94,0.5)",
						}}
					/>
					<Box
						sx={{
							fontSize: "0.75rem",
							color: "#90a4c0",
							letterSpacing: "0.04em",
						}}
					>
						Connected
					</Box>
				</Box>
			</Box>

			{/* Main content */}
			<Box sx={{ flex: 1, display: "flex", minHeight: 0, overflow: "hidden" }}>
				{/* Left: Chat Panel */}
				<Box
					sx={{
						width: "380px",
						flexShrink: 0,
						display: "flex",
						flexDirection: "column",
						borderRight: "1px solid #e3eaf5",
						bgcolor: "#f8fafd",
						minHeight: 0,
						overflow: "hidden",
					}}
				>
					<Box
						sx={{
							px: 3,
							py: 1.5,
							borderBottom: "1px solid #e3eaf5",
							bgcolor: "white",
							flexShrink: 0,
							display: "flex",
							alignItems: "center",
							gap: 1,
						}}
					>
						<Box
							sx={{
								width: 6,
								height: 6,
								borderRadius: "50%",
								bgcolor: "#1976d2",
							}}
						/>
						<Box
							sx={{
								fontSize: "0.7rem",
								fontWeight: 600,
								color: "#90a4c0",
								letterSpacing: "0.1em",
								textTransform: "uppercase",
							}}
						>
							Conversation
						</Box>
					</Box>

					<Box sx={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
						<ChatBox chatMessages={chatMessages} />
					</Box>

					<Box
						sx={{
							p: 2,
							borderTop: "1px solid #e3eaf5",
							flexShrink: 0,
							bgcolor: "white",
						}}
					>
						<InputBox handleSubmit={handleSubmit} />
					</Box>
				</Box>

				{/* Right: Graph Panel */}
				<Box
					sx={{
						flex: 1,
						display: "flex",
						flexDirection: "column",
						minWidth: 0,
						minHeight: 0,
						overflow: "hidden",
						p: 2.5,
					}}
				>
					<GraphBox charts={displayBox} />
				</Box>
			</Box>
		</Box>
	);
}
