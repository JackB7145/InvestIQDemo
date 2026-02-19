"use client";
import { Box, Typography } from "@mui/material";
import { useEffect, useRef } from "react";
import { ChartData } from "../../classes/charts";

interface GraphBoxProps {
	charts: ChartData[];
}

export default function GraphBox({ charts }: GraphBoxProps) {
	const bottomRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [charts]);

	return (
		<Box
			sx={{
				display: "flex",
				flexDirection: "column",
				height: "100%",
				borderRadius: 3,
				overflow: "hidden",
				border: "1px solid #e3eaf5",
			}}
		>
			{/* Header */}
			<Box
				sx={{
					px: 2.5,
					py: 1.5,
					borderBottom: "1px solid #e3eaf5",
					bgcolor: "white",
					display: "flex",
					alignItems: "center",
					justifyContent: "space-between",
				}}
			>
				<Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
					<Box
						sx={{
							width: 8,
							height: 8,
							borderRadius: "50%",
							bgcolor: "#1976d2",
						}}
					/>
					<Typography
						variant="subtitle1"
						sx={{ fontWeight: 600, color: "#1a1a2e", letterSpacing: 0.3 }}
					>
						Graphs
					</Typography>
				</Box>
				{charts.length > 0 && (
					<Typography
						variant="caption"
						sx={{ color: "#90a4c0", fontWeight: 500 }}
					>
						{charts.length} chart{charts.length > 1 ? "s" : ""}
					</Typography>
				)}
			</Box>

			{/* Graph List */}
			<Box
				sx={{
					flex: 1,
					overflowY: "auto",
					px: 2,
					py: 2,
					display: "flex",
					flexDirection: "column",
					gap: 3,
					bgcolor: "#f8fafd",
					"&::-webkit-scrollbar": { width: 6 },
					"&::-webkit-scrollbar-thumb": {
						bgcolor: "#c5d8f5",
						borderRadius: 10,
					},
				}}
			>
				{charts.length === 0 ? (
					<Typography
						sx={{
							color: "#a0aec0",
							textAlign: "center",
							mt: 4,
							fontSize: 14,
							fontStyle: "italic",
						}}
					>
						No charts yet. Select a chart type in the input below.
					</Typography>
				) : (
					charts.map((chart, idx) => (
						<Box
							key={idx}
							sx={{
								bgcolor: "white",
								borderRadius: 2,
								p: 2,
								border: "1px solid #e3eaf5",
								boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
							}}
						>
							{chart.display()}
						</Box>
					))
				)}
				<div ref={bottomRef} />
			</Box>
		</Box>
	);
}
