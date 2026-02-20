"use client";
import { Box, Typography } from "@mui/material";
import ReactMarkdown from "react-markdown";
import { ChatMessage } from "../../page";
import { useEffect, useRef } from "react";

interface ChatBoxProps {
	chatMessages: ChatMessage[];
}

export default function ChatBox({ chatMessages }: ChatBoxProps) {
	const bottomRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [chatMessages]);

	return (
		<Box
			sx={{
				height: "100%",
				overflowY: "auto",
				px: 2,
				py: 2,
				display: "flex",
				flexDirection: "column",
				gap: 2,
				"&::-webkit-scrollbar": { width: "6px" },
				"&::-webkit-scrollbar-track": { bgcolor: "transparent" },
				"&::-webkit-scrollbar-thumb": {
					bgcolor: "#c5d8f5",
					borderRadius: "10px",
				},
			}}
		>
			{chatMessages.length === 0 && (
				<Box
					sx={{
						flex: 1,
						display: "flex",
						flexDirection: "column",
						alignItems: "center",
						justifyContent: "center",
						gap: 2,
						py: 6,
						opacity: 0.6,
					}}
				>
					<Box
						sx={{
							width: 40,
							height: 40,
							borderRadius: "12px",
							border: "1px solid #e3eaf5",
							bgcolor: "white",
							display: "flex",
							alignItems: "center",
							justifyContent: "center",
							boxShadow: "0 2px 8px rgba(25,118,210,0.08)",
						}}
					>
						<svg
							width="18"
							height="18"
							viewBox="0 0 18 18"
							fill="none"
						>
							<path
								d="M9 2C5.13 2 2 5.13 2 9s3.13 7 7 7 7-3.13 7-7-3.13-7-7-7zm0 3c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm0 8c-1.66 0-3-1.34-3-3h1c0 1.1.9 2 2 2s2-.9 2-2h1c0 1.66-1.34 3-3 3z"
								fill="#1976d2"
							/>
						</svg>
					</Box>
					<Typography
						sx={{
							fontSize: "0.78rem",
							color: "#90a4c0",
							textAlign: "center",
							lineHeight: 1.6,
						}}
					>
						Ask me anything.
						<br />I can analyze data and generate charts.
					</Typography>
				</Box>
			)}

			{chatMessages.map((msg, index) => (
				<Box
					key={index}
					sx={{
						display: "flex",
						flexDirection: "column",
						alignItems: msg.type === "user" ? "flex-end" : "flex-start",
					}}
				>
					{/* Role label */}
					{msg.type !== "thinking" && (
						<Box
							sx={{
								fontSize: "0.62rem",
								fontWeight: 600,
								letterSpacing: "0.08em",
								textTransform: "uppercase",
								color: "#90a4c0",
								mb: 0.5,
								px: 0.5,
							}}
						>
							{msg.type === "user" ? "You" : "Assistant"}
						</Box>
					)}

					<Box
						sx={{
							maxWidth: "88%",
							position: "relative",
							...(msg.type === "user" && {
								bgcolor: "#1976d2",
								color: "white",
								px: 2,
								py: 1.25,
								borderRadius: "12px 12px 2px 12px",
								fontSize: "0.85rem",
								lineHeight: 1.6,
								boxShadow: "0 2px 8px rgba(25,118,210,0.25)",
							}),
							...(msg.type === "bot" && {
								bgcolor: "white",
								border: "1px solid #e3eaf5",
								color: "#1a1a2e",
								px: 2,
								py: 1.25,
								borderRadius: "2px 12px 12px 12px",
								fontSize: "0.85rem",
								lineHeight: 1.7,
								boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
								"& p": { m: 0, mb: "0.5em" },
								"& p:last-child": { mb: 0 },
								"& ul, & ol": { m: 0, pl: 2, mb: "0.5em" },
								"& pre": {
									whiteSpace: "pre-wrap",
									m: 0,
									bgcolor: "#f8fafd",
									p: 1.5,
									borderRadius: "6px",
									border: "1px solid #e3eaf5",
									fontSize: "0.8rem",
								},
								"& code": {
									fontSize: "0.8rem",
									bgcolor: "#f0f4fb",
									px: 0.5,
									borderRadius: "3px",
									color: "#1976d2",
								},
								"& strong": { color: "#1a1a2e" },
							}),
							...(msg.type === "thinking" && {
								bgcolor: "rgba(25,118,210,0.04)",
								border: "1px dashed #90c2ff",
								color: "#90a4c0",
								px: 2,
								py: 1.25,
								borderRadius: "2px 12px 12px 12px",
								fontSize: "0.78rem",
								lineHeight: 1.6,
								fontStyle: "italic",
								width: "100%",
							}),
						}}
					>
						{msg.type === "thinking" && (
							<Box
								sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.75 }}
							>
								{[0, 1, 2].map((i) => (
									<Box
										key={i}
										sx={{
											width: 4,
											height: 4,
											borderRadius: "50%",
											bgcolor: "#1976d2",
											animation: "pulse 1.2s ease-in-out infinite",
											animationDelay: `${i * 0.2}s`,
											"@keyframes pulse": {
												"0%, 100%": { opacity: 0.3, transform: "scale(0.8)" },
												"50%": { opacity: 1, transform: "scale(1)" },
											},
										}}
									/>
								))}
								<Box
									sx={{
										fontSize: "0.65rem",
										color: "#1976d2",
										letterSpacing: "0.06em",
										textTransform: "uppercase",
										fontWeight: 600,
										fontStyle: "normal",
									}}
								>
									Reasoning
								</Box>
							</Box>
						)}

						{msg.type === "bot" ? (
							<ReactMarkdown>{msg.text || "..."}</ReactMarkdown>
						) : (
							<Box
								component="span"
								sx={{ whiteSpace: "pre-wrap" }}
							>
								{msg.text}
							</Box>
						)}
					</Box>
				</Box>
			))}

			<div ref={bottomRef} />
		</Box>
	);
}
