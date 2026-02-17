"use client";

import { Box } from "@mui/material";
import { ChartData } from "../../classes/charts"; // base type for charts (LineGraph, BarGraph, ScatterPlotGraph)

interface GraphBoxProps {
  charts: ChartData[]; // array of chart objects
}

export default function GraphBox({ charts }: GraphBoxProps) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", overflowY: "auto", height: "100%", gap: 4 }}>
      {charts.map((chart, idx) => (
        <Box key={idx}>
          {/* Each chart class has its own display() method */}
          {chart.display()}
        </Box>
      ))}
    </Box>
  );
}
