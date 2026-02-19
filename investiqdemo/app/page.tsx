"use client";

import { Box, Typography } from "@mui/material";
import InputBox from "./components/InputBox";
import GraphBox from "./components/GraphBox";
import { useState } from "react";
import ChatBox, { ChatMessage } from "./components/ChatBox";
import { LineGraph, BarGraph, ScatterPlotGraph } from "./classes/charts";

export type ChartItem = LineGraph | BarGraph | ScatterPlotGraph;

// ---------------------------------------------------------------------------
// Thought / response pairs — swap this array out when wiring a real API
// ---------------------------------------------------------------------------
const BOT_EXCHANGES = [
	{
		thought: "Let me figure out what chart the user wants to add...",
		response: "Got it! I've added the chart to the panel on the right.",
	},
	{
		thought:
			"Hmm, analysing the request and picking the right visualisation...",
		response: "Done! The new chart is ready for you.",
	},
	{
		thought: "Checking which data series would best represent this...",
		response: "All set — take a look at the graph panel!",
	},
];

// Async generator that streams a string character by character
async function* streamText(text: string, delayMs = 30) {
	for (const char of text) {
		yield char;
		await new Promise((r) => setTimeout(r, delayMs));
	}
}

const chartKeywords = new Set(["@Line-Graph", "@Bar-Graph", "@Scatter-Plot"]);

export default function Home() {
	const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
	const [chartsState, setChartsState] = useState<ChartItem[]>([]);
	const [exchangeIndex, setExchangeIndex] = useState(0);

	const addChart = (prompt: string) => {
		chartKeywords.forEach((keyword) => {
			if (prompt.includes(keyword)) {
				switch (keyword) {
					case "@Line-Graph":
						setChartsState((prev) => [
							...prev,
							new LineGraph(
								[
									{ name: "Jan", sales: 30, profit: 20 },
									{ name: "Feb", sales: 45, profit: 25 },
									{ name: "Mar", sales: 60, profit: 35 },
								],
								[
									{ key: "sales", color: "#1976d2" },
									{ key: "profit", color: "#42a5f5" },
								],
								"Sample Line Graph",
							),
						]);
						break;
					case "@Bar-Graph":
						setChartsState((prev) => [
							...prev,
							new BarGraph(
								[
									{ name: "Product A", qty: 40 },
									{ name: "Product B", qty: 55 },
									{ name: "Product C", qty: 30 },
								],
								[{ key: "qty", color: "#1976d2" }],
								"Sample Bar Graph",
							),
						]);
						break;
					case "@Scatter-Plot":
						setChartsState((prev) => [
							...prev,
							new ScatterPlotGraph(
								[
									{ x: 5, y: 20 },
									{ x: 10, y: 35 },
									{ x: 15, y: 40 },
									{ x: 20, y: 25 },
								],
								[{ xKey: "x", yKey: "y", color: "#1976d2" }],
								"Sample Scatter Plot",
							),
						]);
						break;
				}
			}
		});
	};

	const handleSubmit = async (prompt: string) => {
		if (!prompt.trim()) return;

		const visibleText = prompt
			.replace(/@Line-Graph|@Bar-Graph|@Scatter-Plot/g, "")
			.trim();

		// 1. Add user message
		setChatMessages((prev) => [
			...prev,
			{ text: visibleText || "(Chart added)", type: "user" },
		]);

		addChart(prompt);

		// Pick the exchange for this turn (cycle through the array)
		const exchange = BOT_EXCHANGES[exchangeIndex % BOT_EXCHANGES.length];
		setExchangeIndex((i) => i + 1);

		// 2. Stream the thought bubble char by char
		const thoughtId = Date.now(); // stable key while streaming
		setChatMessages((prev) => [
			...prev,
			{ text: "", type: "bot", isThought: true, id: thoughtId } as ChatMessage,
		]);

		for await (const char of streamText(exchange.thought, 28)) {
			setChatMessages((prev) =>
				prev.map((m) =>
					(m as any).id === thoughtId ? { ...m, text: m.text + char } : m,
				),
			);
		}

		// Brief pause so user can read the finished thought
		await new Promise((r) => setTimeout(r, 500));

		// 3. Remove thought bubble, stream in response
		setChatMessages((prev) => prev.filter((m) => (m as any).id !== thoughtId));

		const responseId = Date.now();
		setChatMessages((prev) => [
			...prev,
			{
				text: "",
				type: "bot",
				isThought: false,
				id: responseId,
			} as ChatMessage,
		]);

		for await (const char of streamText(exchange.response, 22)) {
			setChatMessages((prev) =>
				prev.map((m) =>
					(m as any).id === responseId ? { ...m, text: m.text + char } : m,
				),
			);
		}
	};

	return (
		<Box
			sx={{
				minWidth: "100vw",
				height: "100vh",
				display: "flex",
				flexDirection: "column",
				bgcolor: "#f0f4fb",
				overflow: "hidden",
			}}
		>
			{/* Top bar */}
			<Box
				sx={{
					px: 4,
					py: 1.5,
					bgcolor: "white",
					borderBottom: "1px solid #e3eaf5",
					display: "flex",
					alignItems: "center",
					gap: 1.5,
					boxShadow: "0 1px 4px rgba(25,118,210,0.06)",
				}}
			>
				<Box
					sx={{
						width: 28,
						height: 28,
						borderRadius: 1.5,
						bgcolor: "#1976d2",
						display: "flex",
						alignItems: "center",
						justifyContent: "center",
					}}
				>
					<Box
						sx={{
							width: 14,
							height: 14,
							bgcolor: "white",
							borderRadius: 0.5,
							opacity: 0.9,
						}}
					/>
				</Box>
				<Typography
					sx={{
						fontWeight: 700,
						fontSize: 16,
						color: "#1a1a2e",
						letterSpacing: 0.4,
					}}
				>
					BettyAI
				</Typography>
			</Box>

			{/* Main content */}
			<Box
				sx={{ flex: 1, display: "flex", gap: 2.5, p: 2.5, overflow: "hidden" }}
			>
				{/* Chat + Input */}
				<Box
					sx={{
						flex: 1,
						minWidth: 280,
						display: "flex",
						flexDirection: "column",
						gap: 2,
					}}
				>
					<Box sx={{ flex: 1, overflow: "hidden" }}>
						<ChatBox chatMessages={chatMessages} />
					</Box>
					<InputBox
						handleSubmit={handleSubmit}
						highlightKeywords={chartKeywords}
					/>
				</Box>

				{/* Graph panel */}
				<Box sx={{ flex: 2, minWidth: 320, overflow: "hidden" }}>
					<GraphBox charts={chartsState} />
				</Box>
			</Box>
		</Box>
	);
}
