"use client";
import { Box } from "@mui/material";
import InputBox from "./components/InputBox";
import GraphBox from "./components/GraphBox";
import { useState, useEffect, useCallback } from "react";
import ChatBox from "./components/ChatBox";
import {
	LineGraph,
	BarGraph,
	ScatterPlotGraph,
	ChartData,
} from "./classes/charts";
import { parseStream, DisplayModule } from "./hooks/useStreamParser";

export interface ChatMessage {
	type: "user" | "bot" | "thinking";
	text: string;
}

type BackendStatus = "checking" | "online" | "offline";

const SUBMIT_TIMEOUT_MS = 180_000;

export default function Home() {
	const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
	const [displayBox, setDisplayBox] = useState<ChartData[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");

	// ── Backend health poll ───────────────────────────────────────────────────
	useEffect(() => {
		const check = () => {
			fetch("/api/health")
				.then((r) => r.json())
				.then((body) =>
					setBackendStatus(body.status === "online" ? "online" : "offline"),
				)
				.catch(() => setBackendStatus("offline"));
		};
		check();
		const interval = setInterval(check, 30_000);
		return () => clearInterval(interval);
	}, []);

	const toolHandlers = useCallback((module: DisplayModule) => {
		const payload = {
			data: module.data,
			layout: module.layout,
			title: module.title,
		};

		if (module.type === "LineGraph") {
			setDisplayBox((prev) => [...prev, LineGraph.fromData(payload)]);
		} else if (module.type === "BarGraph") {
			setDisplayBox((prev) => [...prev, BarGraph.fromData(payload)]);
		} else if (module.type === "ScatterPlot") {
			setDisplayBox((prev) => [...prev, ScatterPlotGraph.fromData(payload)]);
		} else {
			console.warn(`No handler for module type: "${(module as any).type}"`);
		}
	}, []);

	// ── Submit handler ────────────────────────────────────────────────────────
	const handleSubmit = async (prompt: string) => {
		if (!prompt.trim() || isLoading) return;

		setIsLoading(true);

		// Seed user message + empty thinking bubble
		setChatMessages((prev) => [
			...prev,
			{ text: prompt, type: "user" },
			{ text: "", type: "thinking" },
		]);

		const controller = new AbortController();
		const timeoutId = setTimeout(() => controller.abort(), SUBMIT_TIMEOUT_MS);
		let botSeeded = false;

		try {
			const response = await fetch("/api/chat", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ prompt }),
				signal: controller.signal,
			});

			if (!response.ok)
				throw new Error(`HTTP error! status: ${response.status}`);

			await parseStream(response, {
				// Each thinking chunk is a complete status line — append with newline
				onThinking: (text) => {
					setChatMessages((prev) => {
						const updated = [...prev];
						const last = updated[updated.length - 1];
						if (last.type !== "thinking") return prev;
						updated[updated.length - 1] = {
							...last,
							text: last.text ? last.text + "\n" + text : text,
						};
						return updated;
					});
				},

				// First response chunk: flip thinking → bot, then accumulate
				onResponse: (text) => {
					if (!botSeeded) {
						setChatMessages((prev) => {
							const updated = [...prev];
							updated[updated.length - 1] = { text: "", type: "bot" };
							return updated;
						});
						botSeeded = true;
					}
					setChatMessages((prev) => {
						const updated = [...prev];
						const last = updated[updated.length - 1];
						if (last.type !== "bot") return prev;
						updated[updated.length - 1] = {
							...last,
							text: last.text + text,
						};
						return updated;
					});
				},

				onDisplay: (modules) => {
					console.log("Received display modules in page.tsx:", modules);
					modules.forEach(toolHandlers);
				},
			});
		} catch (error) {
			const isAbort =
				error instanceof DOMException && error.name === "AbortError";
			const message = isAbort
				? "Request timed out. Please try again."
				: "Something went wrong. Please try again.";

			if (!isAbort) console.error("Chat API error:", error);

			setChatMessages((prev) => {
				const updated = [...prev];
				updated[updated.length - 1] = { text: message, type: "bot" };
				return updated;
			});
		} finally {
			clearTimeout(timeoutId);
			setIsLoading(false);
		}
	};

	// ── Status indicator config ───────────────────────────────────────────────
	const statusColor: Record<BackendStatus, string> = {
		checking: "#facc15",
		online: "#22c55e",
		offline: "#ef4444",
	};
	const statusLabel: Record<BackendStatus, string> = {
		checking: "Connecting",
		online: "Connected",
		offline: "Offline",
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
							bgcolor: statusColor[backendStatus],
							boxShadow: `0 0 6px ${statusColor[backendStatus]}80`,
							transition: "background-color 0.3s",
						}}
					/>
					<Box
						sx={{
							fontSize: "0.75rem",
							color: "#90a4c0",
							letterSpacing: "0.04em",
						}}
					>
						{statusLabel[backendStatus]}
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
						<InputBox
							handleSubmit={handleSubmit}
							disabled={isLoading}
						/>
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
