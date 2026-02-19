import { Box } from "@mui/material";
import {
	LineChart,
	Line,
	BarChart,
	Bar,
	ScatterChart,
	Scatter,
	XAxis,
	YAxis,
	CartesianGrid,
	Tooltip,
	Legend,
	ResponsiveContainer,
} from "recharts";
import React, { JSX } from "react";

// Base Chart Class
export abstract class ChartData {
	title?: string;
	data: Record<string, any>[];
	constructor(data: Record<string, any>[], title?: string) {
		this.data = data;
		this.title = title;
	}
	abstract display(): JSX.Element;
}

// ----------------- LINE CHART -----------------
export class LineGraph extends ChartData {
	lines: { key: string; color?: string }[];

	constructor(
		data: Record<string, any>[],
		lines: { key: string; color?: string }[],
		title?: string,
	) {
		super(data, title);
		this.lines = lines;
	}

	display() {
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
				{this.title && (
					<Box sx={{ mb: 1, fontWeight: "bold", fontSize: 16 }}>
						{this.title}
					</Box>
				)}
				<ResponsiveContainer
					width="100%"
					height="100%"
				>
					<LineChart data={this.data}>
						<CartesianGrid strokeDasharray="3 3" />
						<XAxis dataKey="name" />
						<YAxis />
						<Tooltip />
						<Legend />
						{this.lines.map((line, idx) => (
							<Line
								key={line.key}
								type="monotone"
								dataKey={line.key}
								stroke={line.color || `hsl(${(idx * 60) % 360}, 70%, 50%)`}
								strokeWidth={2}
							/>
						))}
					</LineChart>
				</ResponsiveContainer>
			</Box>
		);
	}
}

// ----------------- BAR CHART -----------------
export class BarGraph extends ChartData {
	bars: { key: string; color?: string }[];

	constructor(
		data: Record<string, any>[],
		bars: { key: string; color?: string }[],
		title?: string,
	) {
		super(data, title);
		this.bars = bars;
	}

	display() {
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
				{this.title && (
					<Box sx={{ mb: 1, fontWeight: "bold", fontSize: 16 }}>
						{this.title}
					</Box>
				)}
				<ResponsiveContainer
					width="100%"
					height="100%"
				>
					<BarChart data={this.data}>
						<CartesianGrid strokeDasharray="3 3" />
						<XAxis dataKey="name" />
						<YAxis />
						<Tooltip />
						<Legend />
						{this.bars.map((bar, idx) => (
							<Bar
								key={bar.key}
								dataKey={bar.key}
								fill={bar.color || `hsl(${(idx * 60) % 360}, 70%, 50%)`}
							/>
						))}
					</BarChart>
				</ResponsiveContainer>
			</Box>
		);
	}
}

// ----------------- SCATTER PLOT -----------------
export class ScatterPlotGraph extends ChartData {
	scatter: { xKey: string; yKey: string; color?: string }[];

	constructor(
		data: Record<string, any>[],
		scatter: { xKey: string; yKey: string; color?: string }[],
		title?: string,
	) {
		super(data, title);
		this.scatter = scatter;
	}

	display() {
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
				{this.title && (
					<Box sx={{ mb: 1, fontWeight: "bold", fontSize: 16 }}>
						{this.title}
					</Box>
				)}
				<ResponsiveContainer
					width="100%"
					height="100%"
				>
					<ScatterChart>
						<CartesianGrid strokeDasharray="3 3" />
						<XAxis
							type="number"
							dataKey={this.scatter[0]?.xKey}
							name="x"
						/>
						<YAxis
							type="number"
							dataKey={this.scatter[0]?.yKey}
							name="y"
						/>
						<Tooltip cursor={{ strokeDasharray: "3 3" }} />
						<Legend />
						{this.scatter.map((s, idx) => (
							<Scatter
								key={`${s.xKey}-${s.yKey}`}
								data={this.data}
								dataKey={s.yKey}
								fill={s.color || `hsl(${(idx * 60) % 360}, 70%, 50%)`}
							/>
						))}
					</ScatterChart>
				</ResponsiveContainer>
			</Box>
		);
	}
}
