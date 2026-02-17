'use client';

import { Box, Typography } from "@mui/material";

interface ChatMessage {
  type: "bot" | "user";
  text: string;
}

interface ThinkingBoxProps {
  chatMessages: ChatMessage[];
}

export default function ThinkingBox({ chatMessages }: ThinkingBoxProps) {
  return (
    <Box
      sx={{
        p: 2,
        border: "1px solid #ccc",
        borderRadius: 2,
        display: "flex",
        flexDirection: "column",
        height: "100%",         
        overflowY: "auto",       
        bgcolor: "white",
      }}
    >
      <Typography variant="h6" sx={{ mb: 2 }}>
        Chat Window
      </Typography>

      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          gap: 1,
        }}
      >
        {chatMessages.length === 0 && (
          <Typography sx={{ color: "gray", textAlign: "center" }}>
            Waiting for messages...
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
            <Box
              sx={{
                maxWidth: "70%",
                bgcolor: msg.type === "user" ? "primary.main" : "grey.300",
                color: msg.type === "user" ? "white" : "black",
                p: 1.5,
                borderRadius: 2,
                wordBreak: "break-word",
              }}
            >
              {msg.text || (msg.type === "bot" ? "Bot is thinking..." : "")}
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
