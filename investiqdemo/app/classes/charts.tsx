"use client";
import { Box } from "@mui/material";
import React, { useEffect, useRef } from "react";

export function PlotlyChart({ data, layout }: { data: any[]; layout: any }) {
	const chartRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!data || data.length === 0) return;

		import("plotly.js-dist-min").then((Plotly) => {
			if (!chartRef.current) return;

			const safeLayout = layout ?? {};

			const hasDateX = data.some(
				(trace) =>
					Array.isArray(trace.x) &&
					typeof trace.x[0] === "string" &&
					/^\d{4}-\d{2}-\d{2}/.test(trace.x[0]),
			);

			const mergedLayout = {
				...safeLayout,
				autosize: true,
				height: 400,
				paper_bgcolor: "rgba(0,0,0,0)",
				plot_bgcolor: "rgba(0,0,0,0)",
				margin: { t: 80, r: 30, b: 60, l: 70 },
				font: { family: "Inter, sans-serif", size: 12 },
				title: safeLayout.title
					? {
							text:
								typeof safeLayout.title === "string"
									? safeLayout.title
									: safeLayout.title.text,
							font: { size: 15, color: "#1a1a2e", weight: 600 },
							x: 0.05,
						}
					: undefined,
				xaxis: {
					...(safeLayout.xaxis ?? {}),
					...(hasDateX && {
						type: "date",
						tickformat: "%b %d '%y",
						tickangle: -30,
						nticks: 10,
						showgrid: true,
						gridcolor: "#e3eaf5",
					}),
					title: {
						text:
							safeLayout.xaxis?.title?.text ?? safeLayout.xaxis?.title ?? "",
						font: { size: 12, color: "#64748b" },
						standoff: 12,
					},
				},
				yaxis: {
					showgrid: true,
					gridcolor: "#e3eaf5",
					...(safeLayout.yaxis ?? {}),
					title: {
						text:
							safeLayout.yaxis?.title?.text ?? safeLayout.yaxis?.title ?? "",
						font: { size: 12, color: "#64748b" },
						standoff: 12,
					},
				},
			};

			Plotly.newPlot(chartRef.current, data, mergedLayout, {
				responsive: true,
				displayModeBar: "hover",
				modeBarButtonsToRemove: ["lasso2d", "select2d"],
			});
		});
	}, [data, layout]);

	return (
		<Box sx={{ width: "100%", borderRadius: 2, overflow: "hidden" }}>
			<div
				ref={chartRef}
				style={{ width: "100%", display: "block" }}
			/>
		</Box>
	);
}
// ── Data classes ──────────────────────────────────────────────────────────────
export class ChartData {
	type: string;
	data: any[];
	layout: any;
	title?: string;

	constructor(type: string, data: any[], layout?: any, title?: string) {
		this.type = type;
		this.data = data;
		// Don't mutate the incoming layout object — clone it
		this.layout = layout ? { ...layout } : {};
		// Only set title if not already present in layout
		if (title && !this.layout.title) {
			this.layout.title = title;
		}
		this.title = title;
	}
}

export class LineGraph extends ChartData {
	static fromData(payload: { data: any[]; layout?: any; title?: string }) {
		return new LineGraph(
			"LineGraph",
			payload.data,
			payload.layout,
			payload.title,
		);
	}
}
export class BarGraph extends ChartData {
	static fromData(payload: { data: any[]; layout?: any; title?: string }) {
		return new BarGraph(
			"BarGraph",
			payload.data,
			payload.layout,
			payload.title,
		);
	}
}
export class ScatterPlotGraph extends ChartData {
	static fromData(payload: { data: any[]; layout?: any; title?: string }) {
		return new ScatterPlotGraph(
			"ScatterPlot",
			payload.data,
			payload.layout,
			payload.title,
		);
	}
}
