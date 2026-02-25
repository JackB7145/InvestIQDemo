"use client";
import { Box } from "@mui/material";
import Plotly from "plotly.js-dist-min";
import React, { JSX, useEffect, useRef } from "react";

// Base Chart Class
export abstract class ChartData {
	title?: string;
	data: any[];
	layout: any;

	constructor(data: any[], layout?: any, title?: string) {
		this.data = data;
		this.layout = layout || {};
		if (title) this.layout.title = title;
		this.title = title;
	}

	abstract display(): JSX.Element;
}

// ----------------- LINE GRAPH -----------------
export class LineGraph extends ChartData {
	static fromData(payload: { data: any[]; layout?: any; title?: string }) {
		return new LineGraph(payload.data, payload.layout, payload.title);
	}

	display() {
		const chartRef = useRef<HTMLDivElement>(null);

		useEffect(() => {
			if (chartRef.current) {
				Plotly.newPlot(chartRef.current, this.data, this.layout, {
					responsive: true,
				});
			}
		}, [chartRef, this.data, this.layout]);

		return (
			<Box
				sx={{
					width: "100%",
					height: 300,
					p: 2,
					bgcolor: "white",
					borderRadius: 2,
					boxShadow: 1,
				}}
			>
				<div
					ref={chartRef}
					style={{ width: "100%", height: "100%" }}
				/>
			</Box>
		);
	}
}

// ----------------- BAR GRAPH -----------------
export class BarGraph extends ChartData {
	static fromData(payload: { data: any[]; layout?: any; title?: string }) {
		return new BarGraph(payload.data, payload.layout, payload.title);
	}

	display() {
		const chartRef = useRef<HTMLDivElement>(null);

		useEffect(() => {
			if (chartRef.current) {
				Plotly.newPlot(chartRef.current, this.data, this.layout, {
					responsive: true,
				});
			}
		}, [chartRef, this.data, this.layout]);

		return (
			<Box
				sx={{
					width: "100%",
					height: 300,
					p: 2,
					bgcolor: "white",
					borderRadius: 2,
					boxShadow: 1,
				}}
			>
				<div
					ref={chartRef}
					style={{ width: "100%", height: "100%" }}
				/>
			</Box>
		);
	}
}

// ----------------- SCATTER PLOT -----------------
export class ScatterPlotGraph extends ChartData {
	static fromData(payload: { data: any[]; layout?: any; title?: string }) {
		return new ScatterPlotGraph(payload.data, payload.layout, payload.title);
	}

	display() {
		const chartRef = useRef<HTMLDivElement>(null);

		useEffect(() => {
			if (chartRef.current) {
				Plotly.newPlot(chartRef.current, this.data, this.layout, {
					responsive: true,
				});
			}
		}, [chartRef, this.data, this.layout]);

		return (
			<Box
				sx={{
					width: "100%",
					height: 300,
					p: 2,
					bgcolor: "white",
					borderRadius: 2,
					boxShadow: 1,
				}}
			>
				<div
					ref={chartRef}
					style={{ width: "100%", height: "100%" }}
				/>
			</Box>
		);
	}
}
