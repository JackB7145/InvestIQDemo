"use client";

import { Box, IconButton, Tooltip } from "@mui/material";
import { useState, useRef } from "react";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";

interface InputBoxParameters {
  handleSubmit: (prompt: string) => void;
  highlightKeywords?: Set<string>;
}

export default function InputBox({ handleSubmit, highlightKeywords }: InputBoxParameters) {
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

  // Highlight keywords
  const highlightedText = prompt.split(/(\s+)/).map((word, idx) => {
    if (highlightKeywords?.has(word)) {
      return (
        <mark
          key={idx}
          style={{ backgroundColor: "rgba(255, 235, 59, 0.4)", color: "black" }}
        >
          {word}
        </mark>
      );
    }
    return word;
  });

  return (
    <Box sx={{ position: "relative", p: 0 }}>
      <Box
        sx={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          padding: "0.5rem",
          pointerEvents: "none",
          color: "transparent",
          whiteSpace: "pre-wrap",
          wordWrap: "break-word",
          fontFamily: "inherit",
          fontSize: "inherit",
          lineHeight: "inherit",
          overflow: "hidden",
          zIndex: 0,
        }}
      >
        <div style={{ position: "relative", top: -scrollTop }}>{highlightedText}</div>
      </Box>

      {/* Actual textarea */}
      <textarea
        ref={textareaRef}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={handleKeyDown}
        onScroll={handleScroll}
        className="w-full bg-transparent border border-gray-300 rounded-md p-2 resize-none focus:outline-none focus:ring-0 focus:border-gray-300 relative z-10"
        placeholder="Enter prompt here..."
        rows={4}
      />

      <Tooltip title="Submit Prompt">
        <IconButton
          onClick={onSubmit}
          sx={{
            position: "absolute",
            bottom: 5,
            right: 5,
            border: "2px solid",
            borderColor: "primary.main",
            color: "primary.main",
            "&:hover": {
              backgroundColor: "primary.light",
              borderColor: "primary.dark",
              color: "white",
            },
            width: 30,
            height: 30,
            zIndex: 20,
          }}
        >
          <ArrowUpwardIcon />
        </IconButton>
      </Tooltip>
    </Box>
  );
}
