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
		setChatMessages((prev) => [...prev, { text: prompt, type: "user" }]);
		setChatMessages((prev) => [...prev, { text: "", type: "thinking" }]);

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

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;
				const chunk = decoder.decode(value);

				if (chunk.startsWith("thought:")) {
					const thoughtChunk = chunk.slice(8);
					setChatMessages((prev) => {
						const updated = [...prev];
						updated[updated.length - 1] = {
							...updated[updated.length - 1],
							text: updated[updated.length - 1].text + thoughtChunk,
						};
						return updated;
					});
				} else if (chunk.startsWith("text:")) {
					if (!botSeeded) {
						setChatMessages((prev) => {
							const updated = [...prev];
							updated[updated.length - 1] = { text: "", type: "bot" };
							return updated;
						});
						botSeeded = true;
					}
					const textChunk = chunk.slice(5);
					setChatMessages((prev) => {
						const updated = [...prev];
						updated[updated.length - 1] = {
							...updated[updated.length - 1],
							text: updated[updated.length - 1].text + textChunk,
						};
						return updated;
					});
				} else if (chunk.startsWith("tools:")) {
					const toolsResponse = JSON.parse(chunk.slice(6));
					toolsResponse.forEach((tool: { type: string; data: any }) => {
						const handler = toolHandlers[tool.type];
						if (handler) handler(tool.data);
						else console.warn(`No handler for tool type: "${tool.type}"`);
					});
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
				height: "100vh", // fixed height — children can fill & scroll
				width: "100vw",
				display: "flex",
				flexDirection: "column",
				bgcolor: "#0a0a0f",
				fontFamily: "'DM Sans', sans-serif",
				overflow: "hidden", // page itself never scrolls
			}}
		>
			{/* Header */}
			<Box
				sx={{
					px: 4,
					py: 2,
					display: "flex",
					alignItems: "center",
					justifyContent: "space-between",
					borderBottom: "1px solid rgba(255,255,255,0.06)",
					bgcolor: "rgba(255,255,255,0.02)",
					backdropFilter: "blur(12px)",
					flexShrink: 0,
				}}
			>
				<Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
					<Box
						sx={{
							width: 32,
							height: 32,
							borderRadius: "8px",
							background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
							display: "flex",
							alignItems: "center",
							justifyContent: "center",
							boxShadow: "0 0 20px rgba(99,102,241,0.4)",
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
							fontWeight: 600,
							color: "white",
							letterSpacing: "-0.02em",
							fontFamily: "'DM Sans', sans-serif",
						}}
					>
						Analyst
					</Box>
					<Box
						component="span"
						sx={{
							fontSize: "0.65rem",
							fontWeight: 500,
							color: "#6366f1",
							bgcolor: "rgba(99,102,241,0.12)",
							border: "1px solid rgba(99,102,241,0.25)",
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
				<Box sx={{ display: "flex", alignItems: "center", gap: 3 }}>
					<Box
						sx={{
							width: 8,
							height: 8,
							borderRadius: "50%",
							bgcolor: "#22c55e",
							boxShadow: "0 0 8px #22c55e",
						}}
					/>
					<Box
						sx={{
							fontSize: "0.75rem",
							color: "rgba(255,255,255,0.35)",
							letterSpacing: "0.04em",
						}}
					>
						Connected
					</Box>
				</Box>
			</Box>

			{/* Main content — takes all remaining height */}
			<Box
				sx={{
					flex: 1,
					display: "flex",
					minHeight: 0, // KEY: lets flex children shrink below content size
					overflow: "hidden",
				}}
			>
				{/* Left: Chat Panel */}
				<Box
					sx={{
						width: "380px",
						flexShrink: 0,
						display: "flex",
						flexDirection: "column",
						borderRight: "1px solid rgba(255,255,255,0.06)",
						minHeight: 0, // KEY: allows internal flex to work
						overflow: "hidden",
					}}
				>
					{/* Panel label */}
					<Box
						sx={{
							px: 3,
							py: 2,
							borderBottom: "1px solid rgba(255,255,255,0.06)",
							flexShrink: 0,
						}}
					>
						<Box
							sx={{
								fontSize: "0.7rem",
								fontWeight: 600,
								color: "rgba(255,255,255,0.3)",
								letterSpacing: "0.1em",
								textTransform: "uppercase",
							}}
						>
							Conversation
						</Box>
					</Box>

					{/* Scrollable messages */}
					<Box sx={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
						<ChatBox chatMessages={chatMessages} />
					</Box>

					{/* Pinned input */}
					<Box
						sx={{
							p: 2,
							borderTop: "1px solid rgba(255,255,255,0.06)",
							flexShrink: 0,
							bgcolor: "rgba(255,255,255,0.01)",
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
						minHeight: 0, // KEY
						overflow: "hidden",
					}}
				>
					{/* Panel label */}
					<Box
						sx={{
							px: 3,
							py: 2,
							borderBottom: "1px solid rgba(255,255,255,0.06)",
							display: "flex",
							alignItems: "center",
							justifyContent: "space-between",
							flexShrink: 0,
						}}
					>
						<Box
							sx={{
								fontSize: "0.7rem",
								fontWeight: 600,
								color: "rgba(255,255,255,0.3)",
								letterSpacing: "0.1em",
								textTransform: "uppercase",
							}}
						>
							Visualizations
						</Box>
						<Box sx={{ fontSize: "0.7rem", color: "rgba(255,255,255,0.2)" }}>
							{displayBox.length} chart{displayBox.length !== 1 ? "s" : ""}
						</Box>
					</Box>

					{/* Scrollable charts — THIS is what was broken before */}
					<Box sx={{ flex: 1, minHeight: 0, overflowY: "auto", p: 3 }}>
						<GraphBox charts={displayBox} />
					</Box>
				</Box>
			</Box>
		</Box>
	);
}
