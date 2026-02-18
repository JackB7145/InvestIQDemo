"use client";
import { Box, Typography } from "@mui/material";
import { ChartData } from "../../classes/charts";

interface GraphBoxProps {
	charts: ChartData[];
}

export default function GraphBox({ charts }: GraphBoxProps) {
	if (charts.length === 0) {
		return (
			<Box
				sx={{
					display: "flex",
					flexDirection: "column",
					alignItems: "center",
					justifyContent: "center",
					gap: 2.5,
					opacity: 0.35,
				}}
			>
				{/* Decorative grid */}
				<Box sx={{ position: "relative", width: 80, height: 60 }}>
					{[0, 1, 2, 3].map((col) =>
						[0, 1, 2].map((row) => (
							<Box
								key={`${col}-${row}`}
								sx={{
									position: "absolute",
									left: col * 22,
									bottom: row * 22,
									width: 16,
									height: (row + 1) * 14 + col * 4,
									bgcolor: "rgba(99,102,241,0.5)",
									borderRadius: "3px 3px 0 0",
									opacity: 0.3 + (col + row) * 0.1,
								}}
							/>
						)),
					)}
				</Box>
				<Box sx={{ textAlign: "center" }}>
					<Typography
						sx={{
							fontSize: "0.85rem",
							color: "rgba(255,255,255,0.5)",
							fontWeight: 500,
							mb: 0.5,
						}}
					>
						No visualizations yet
					</Typography>
					<Typography
						sx={{
							fontSize: "0.75rem",
							color: "rgba(255,255,255,0.25)",
							lineHeight: 1.5,
						}}
					>
						Ask for a chart or graph to see it here
					</Typography>
				</Box>
			</Box>
		);
	}

	return (
		<Box
			sx={{
				height: "100%",
				overflowY: "auto",
				display: "flex",
				flexDirection: "column",
				gap: 3,
				pr: 1,
				"&::-webkit-scrollbar": { width: "4px" },
				"&::-webkit-scrollbar-track": { bgcolor: "transparent" },
				"&::-webkit-scrollbar-thumb": {
					bgcolor: "rgba(255,255,255,0.1)",
					borderRadius: "4px",
				},
			}}
		>
			{charts.map((chart, idx) => (
				<Box
					key={idx}
					sx={{
						bgcolor: "rgba(255,255,255,0.03)",
						border: "1px solid rgba(255,255,255,0.07)",
						borderRadius: "12px",
						p: 2.5,
						transition: "border-color 0.2s ease",
						"&:hover": {
							borderColor: "rgba(99,102,241,0.2)",
						},
					}}
				>
					<Box
						sx={{
							display: "flex",
							alignItems: "center",
							justifyContent: "space-between",
							mb: 2,
						}}
					>
						<Box
							sx={{
								display: "flex",
								alignItems: "center",
								gap: 1,
							}}
						>
							<Box
								sx={{
									width: 6,
									height: 6,
									borderRadius: "50%",
									bgcolor: "#6366f1",
									boxShadow: "0 0 6px rgba(99,102,241,0.6)",
								}}
							/>
							<Typography
								sx={{
									fontSize: "0.68rem",
									fontWeight: 600,
									letterSpacing: "0.08em",
									textTransform: "uppercase",
									color: "rgba(255,255,255,0.25)",
								}}
							>
								Chart {idx + 1}
							</Typography>
						</Box>
						<Box
							sx={{
								fontSize: "0.65rem",
								color: "rgba(255,255,255,0.15)",
								bgcolor: "rgba(255,255,255,0.04)",
								border: "1px solid rgba(255,255,255,0.06)",
								px: 1,
								py: 0.25,
								borderRadius: "4px",
								letterSpacing: "0.04em",
							}}
						>
							Generated
						</Box>
					</Box>
					{chart.display()}
				</Box>
			))}
		</Box>
	);
}
