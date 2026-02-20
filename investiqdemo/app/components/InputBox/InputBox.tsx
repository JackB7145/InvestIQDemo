"use client";
import { Box, IconButton, Tooltip } from "@mui/material";
import { useState, useRef, KeyboardEvent } from "react";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";

interface InputBoxProps {
	handleSubmit: (prompt: string) => void;
}

export default function InputBox({ handleSubmit }: InputBoxProps) {
	const [value, setValue] = useState("");
	const textareaRef = useRef<HTMLTextAreaElement>(null);

	const submit = () => {
		if (!value.trim()) return;
		handleSubmit(value.trim());
		setValue("");
		if (textareaRef.current) {
			textareaRef.current.style.height = "auto";
		}
	};

	const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			submit();
		}
	};

	const handleInput = () => {
		const el = textareaRef.current;
		if (!el) return;
		el.style.height = "auto";
		el.style.height = Math.min(el.scrollHeight, 120) + "px";
	};

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
				<textarea
					ref={textareaRef}
					value={value}
					onChange={(e) => setValue(e.target.value)}
					onKeyDown={handleKeyDown}
					onInput={handleInput}
					placeholder="Ask a question or request a chart..."
					rows={3}
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
						minHeight: "24px",
						maxHeight: "120px",
					}}
				/>
				<Tooltip title="Send">
					<IconButton
						onClick={submit}
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
