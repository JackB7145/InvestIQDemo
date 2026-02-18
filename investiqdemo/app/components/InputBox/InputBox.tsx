"use client";
import { Box, IconButton } from "@mui/material";
import { useState, useRef, KeyboardEvent } from "react";

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
				display: "flex",
				alignItems: "flex-end",
				gap: 1.5,
				bgcolor: "rgba(255,255,255,0.04)",
				border: "1px solid rgba(255,255,255,0.08)",
				borderRadius: "12px",
				px: 2,
				py: 1.25,
				transition: "border-color 0.15s ease",
				"&:focus-within": {
					borderColor: "rgba(99,102,241,0.4)",
					bgcolor: "rgba(99,102,241,0.03)",
				},
			}}
		>
			<textarea
				ref={textareaRef}
				value={value}
				onChange={(e) => setValue(e.target.value)}
				onKeyDown={handleKeyDown}
				onInput={handleInput}
				placeholder="Ask a question or request a chart..."
				rows={1}
				style={{
					flex: 1,
					background: "transparent",
					border: "none",
					outline: "none",
					resize: "none",
					color: "rgba(255,255,255,0.87)",
					fontSize: "0.85rem",
					lineHeight: "1.6",
					fontFamily: "'DM Sans', sans-serif",
					caretColor: "#6366f1",
					minHeight: "24px",
					maxHeight: "120px",
				}}
			/>
			<Box
				component="button"
				onClick={submit}
				disabled={!value.trim()}
				sx={{
					flexShrink: 0,
					width: 32,
					height: 32,
					borderRadius: "8px",
					border: "none",
					cursor: value.trim() ? "pointer" : "not-allowed",
					background: value.trim()
						? "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)"
						: "rgba(255,255,255,0.06)",
					display: "flex",
					alignItems: "center",
					justifyContent: "center",
					transition: "all 0.15s ease",
					boxShadow: value.trim() ? "0 0 12px rgba(99,102,241,0.35)" : "none",
					"&:hover": value.trim()
						? {
								transform: "scale(1.05)",
								boxShadow: "0 0 18px rgba(99,102,241,0.5)",
							}
						: {},
				}}
			>
				<svg
					width="14"
					height="14"
					viewBox="0 0 14 14"
					fill="none"
				>
					<path
						d="M7 12V2M3 6l4-4 4 4"
						stroke={value.trim() ? "white" : "rgba(255,255,255,0.2)"}
						strokeWidth="1.75"
						strokeLinecap="round"
						strokeLinejoin="round"
					/>
				</svg>
			</Box>
		</Box>
	);
}
