"use client";
import { Box, IconButton, Tooltip } from "@mui/material";
import { useState, useRef } from "react";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";

interface InputBoxParameters {
	handleSubmit: (prompt: string) => void;
	highlightKeywords?: Set<string>;
}

export default function InputBox({
	handleSubmit,
	highlightKeywords,
}: InputBoxParameters) {
	const [prompt, setPrompt] = useState("");
	const textareaRef = useRef<HTMLTextAreaElement>(null);
	const [scrollTop, setScrollTop] = useState(0);

	const onSubmit = () => {
		if (!prompt.trim()) return;
		handleSubmit(prompt);
		setPrompt("");
	};

	const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			onSubmit();
		}
	};

	const handleScroll = () => {
		if (textareaRef.current) setScrollTop(textareaRef.current.scrollTop);
	};

	const highlightedText = prompt.split(/(\s+)/).map((word, idx) => {
		if (highlightKeywords?.has(word)) {
			return (
				<mark
					key={idx}
					style={{
						backgroundColor: "rgba(25, 118, 210, 0.15)",
						color: "#1976d2",
						borderRadius: 3,
					}}
				>
					{word}
				</mark>
			);
		}
		return word;
	});

	return (
		<Box
			sx={{
				border: "1px solid #e3eaf5",
				borderRadius: 3,
				bgcolor: "white",
				overflow: "hidden",
				boxShadow: "0 2px 12px rgba(25,118,210,0.08)",
				transition: "box-shadow 0.2s, border-color 0.2s",
				"&:focus-within": {
					boxShadow: "0 2px 16px rgba(25,118,210,0.18)",
					borderColor: "#90c2ff",
				},
			}}
		>
			<Box sx={{ position: "relative", px: 2, py: 1.5 }}>
				{/* Highlight overlay */}
				<Box
					sx={{
						position: "absolute",
						top: 0,
						left: 0,
						width: "100%",
						height: "100%",
						padding: "12px 16px",
						pointerEvents: "none",
						color: "transparent",
						whiteSpace: "pre-wrap",
						wordWrap: "break-word",
						fontFamily: "inherit",
						fontSize: 14,
						lineHeight: 1.6,
						overflow: "hidden",
						zIndex: 0,
					}}
				>
					<div style={{ position: "relative", top: -scrollTop }}>
						{highlightedText}
					</div>
				</Box>

				{/* Textarea */}
				<textarea
					ref={textareaRef}
					value={prompt}
					onChange={(e) => setPrompt(e.target.value)}
					onKeyDown={handleKeyDown}
					onScroll={handleScroll}
					style={{
						width: "100%",
						background: "transparent",
						border: "none",
						outline: "none",
						resize: "none",
						fontFamily: "inherit",
						fontSize: 14,
						lineHeight: 1.6,
						color: "#1a1a2e",
						paddingRight: 44,
						boxSizing: "border-box",
						position: "relative",
						zIndex: 10,
					}}
					placeholder="Type your message... use @Line-Graph, @Bar-Graph, @Scatter-Plot to add charts"
					rows={3}
				/>

				<Tooltip title="Send">
					<IconButton
						onClick={onSubmit}
						sx={{
							position: "absolute",
							bottom: 10,
							right: 10,
							bgcolor: "#1976d2",
							color: "white",
							width: 32,
							height: 32,
							zIndex: 20,
							"&:hover": { bgcolor: "#1565c0" },
							boxShadow: "0 2px 8px rgba(25,118,210,0.3)",
							transition: "all 0.15s",
						}}
					>
						<ArrowUpwardIcon sx={{ fontSize: 18 }} />
					</IconButton>
				</Tooltip>
			</Box>
		</Box>
	);
}
