"use client";
import { Box, Typography } from "@mui/material";
import { useEffect, useRef } from "react";

export interface ChatMessage {
	type: "bot" | "user";
	text: string;
	isThought?: boolean;
	id?: number;
}

interface ChatBoxProps {
	chatMessages: ChatMessage[];
}

function ThoughtBubble({ text }: { text: string }) {
	return (
		<Box
			sx={{
				maxWidth: "72%",
				px: 2,
				py: 1.2,
				borderRadius: "18px 18px 18px 4px",
				bgcolor: "#f0f6ff",
				color: "#5a82b4",
				fontSize: 13,
				lineHeight: 1.6,
				fontStyle: "italic",
				wordBreak: "break-word",
				border: "1.5px dashed #90bff5",
				boxShadow: "none",
				animation: "fadeIn 0.2s ease-in",
				"@keyframes fadeIn": {
					from: { opacity: 0, transform: "translateY(4px)" },
					to: { opacity: 1, transform: "translateY(0)" },
				},
			}}
		>
			💭 {text}
		</Box>
	);
}

export default function ChatBox({ chatMessages }: ChatBoxProps) {
	const bottomRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [chatMessages]);

	return (
		<Box
			sx={{
				display: "flex",
				flexDirection: "column",
				height: "100%",
				borderRadius: 3,
				overflow: "hidden",
				border: "1px solid #e3eaf5",
			}}
		>
			{/* Header */}
			<Box
				sx={{
					px: 2.5,
					py: 1.5,
					borderBottom: "1px solid #e3eaf5",
					bgcolor: "white",
					display: "flex",
					alignItems: "center",
					gap: 1,
				}}
			>
				<Box
					sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: "#1976d2" }}
				/>
				<Typography
					variant="subtitle1"
					sx={{ fontWeight: 600, color: "#1a1a2e", letterSpacing: 0.3 }}
				>
					Chat
				</Typography>
			</Box>

			{/* Messages */}
			<Box
				sx={{
					flex: 1,
					overflowY: "auto",
					px: 2,
					py: 2,
					display: "flex",
					flexDirection: "column",
					gap: 1.5,
					bgcolor: "#f8fafd",
					"&::-webkit-scrollbar": { width: 6 },
					"&::-webkit-scrollbar-thumb": {
						bgcolor: "#c5d8f5",
						borderRadius: 10,
					},
				}}
			>
				{chatMessages.length === 0 && (
					<Typography
						sx={{
							color: "#a0aec0",
							textAlign: "center",
							mt: 4,
							fontSize: 14,
							fontStyle: "italic",
						}}
					>
						Start the conversation...
					</Typography>
				)}

				{chatMessages.map((msg, index) => (
					<Box
						key={index}
						sx={{
							display: "flex",
							justifyContent: msg.type === "user" ? "flex-end" : "flex-start",
						}}
					>
						{msg.isThought ? (
							<ThoughtBubble text={msg.text} />
						) : (
							<Box
								sx={{
									maxWidth: "72%",
									px: 2,
									py: 1.2,
									borderRadius:
										msg.type === "user"
											? "18px 18px 4px 18px"
											: "18px 18px 18px 4px",
									bgcolor: msg.type === "user" ? "#1976d2" : "white",
									color: msg.type === "user" ? "white" : "#1a1a2e",
									fontSize: 14,
									lineHeight: 1.6,
									wordBreak: "break-word",
									boxShadow:
										msg.type === "user"
											? "0 2px 8px rgba(25,118,210,0.25)"
											: "0 1px 4px rgba(0,0,0,0.08)",
									border: msg.type === "bot" ? "1px solid #e3eaf5" : "none",
									animation: "fadeIn 0.25s ease-in",
									"@keyframes fadeIn": {
										from: { opacity: 0, transform: "translateY(4px)" },
										to: { opacity: 1, transform: "translateY(0)" },
									},
								}}
							>
								{msg.text}
							</Box>
						)}
					</Box>
				))}
				<div ref={bottomRef} />
			</Box>
		</Box>
	);
}
