"use client";

import { Box } from "@mui/material";
import InputBox from "./components/InputBox";
import GraphBox from "./components/GraphBox";
import { useState } from "react";
import ChatBox from "./components/ChatBox";
import { LineGraph, BarGraph, ScatterPlotGraph } from "./classes/charts"; // assuming charts classes exist

interface ChatMessage {
  type: "user" | "bot";
  text: string;
}

export type ChartItem = LineGraph | BarGraph | ScatterPlotGraph;

export default function Home() {
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chartsState, setChartsState] = useState<ChartItem[]>([]);

  const chartKeywords = new Set(["@Line-Graph", "@Bar-Graph", "@Scatter-Plot"]);

  // ---------------- ADD CHART METHOD ----------------
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
                { key: "profit", color: "#ff5722" },
              ],
              "Sample Line Graph"
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
              [{ key: "qty", color: "#4caf50" }],
              "Sample Bar Graph"
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
              [{ xKey: "x", yKey: "y", color: "#9c27b0" }],
              "Sample Scatter Plot"
            ),
          ]);
          break;
      }
    }
  });
};

  // ---------------- HANDLE USER SUBMIT ----------------
  const handleSubmit = (prompt: string) => {
    if (!prompt.trim()) return;

    // Add user message
    setChatMessages((prev) => [
      ...prev,
      { text: prompt, type: "user" },
    ]);

    // Check for chart keywords and add charts dynamically
    addChart(prompt);

    // Simulate bot response
    setTimeout(() => {
      setChatMessages((prev) => [
        ...prev,
        { text: "This is a temporary bot response.", type: "bot" },
      ]);
    }, 500);
  };

  return (
    <Box
      sx={{
        minWidth: "100vw",
        maxHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        gap: 4,
        bgcolor: "grey.100",
        p: 4,
      }}
    >
      <Box
        sx={{
          display: "flex",
          gap: 4,
          flexWrap: "wrap",
        }}
      >
        {/* Chat Section */}
        <Box
          sx={{
            flex: 1,
            minWidth: 300,
            p: 2,
            bgcolor: "white",
            borderRadius: 2,
            boxShadow: 1,
            height: "80vh",
          }}
        >
          <ChatBox chatMessages={chatMessages} />
        </Box>

        {/* Graph Section */}
        <Box
          sx={{
            flex: 2,
            minWidth: 300,
            p: 2,
            bgcolor: "white",
            borderRadius: 2,
            boxShadow: 1,
            height: "80vh"
          }}
        >
          <GraphBox charts={chartsState} />
        </Box>
      </Box>

      {/* Input Section */}
      <Box
        sx={{
          p: 2,
          bgcolor: "white",
          borderRadius: 2,
          boxShadow: 1,
          minHeight: "10vh",
        }}
      >
        <InputBox handleSubmit={handleSubmit} />
      </Box>
    </Box>
  );
}
