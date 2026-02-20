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
					flexShrink: 0,
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
						Visualizations
					</Typography>
				</Box>
				{charts.length > 0 && (
					<Typography
						variant="caption"
						sx={{ color: "#90a4c0", fontWeight: 500 }}
					>
						{charts.length} chart{charts.length !== 1 ? "s" : ""}
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
					<Box
						sx={{
							display: "flex",
							flexDirection: "column",
							alignItems: "center",
							justifyContent: "center",
							gap: 2,
							mt: 6,
							opacity: 0.6,
						}}
					>
						{/* Decorative bar chart illustration */}
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
											bgcolor: "rgba(25,118,210,0.25)",
											borderRadius: "3px 3px 0 0",
											opacity: 0.3 + (col + row) * 0.1,
										}}
									/>
								)),
							)}
						</Box>
						<Typography
							sx={{
								color: "#a0aec0",
								textAlign: "center",
								fontSize: 14,
								fontStyle: "italic",
							}}
						>
							No charts yet. Ask for a graph to see it here.
						</Typography>
					</Box>
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
								transition: "border-color 0.2s ease, box-shadow 0.2s ease",
								"&:hover": {
									borderColor: "#90c2ff",
									boxShadow: "0 2px 12px rgba(25,118,210,0.1)",
								},
							}}
						>
							{/* Chart label row */}
							<Box
								sx={{
									display: "flex",
									alignItems: "center",
									justifyContent: "space-between",
									mb: 1.5,
								}}
							>
								<Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
									<Box
										sx={{
											width: 6,
											height: 6,
											borderRadius: "50%",
											bgcolor: "#1976d2",
										}}
									/>
									<Typography
										sx={{
											fontSize: "0.68rem",
											fontWeight: 600,
											letterSpacing: "0.08em",
											textTransform: "uppercase",
											color: "#90a4c0",
										}}
									>
										Chart {idx + 1}
									</Typography>
								</Box>
								<Box
									sx={{
										fontSize: "0.65rem",
										color: "#90a4c0",
										bgcolor: "#f0f4fb",
										border: "1px solid #e3eaf5",
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
					))
				)}
				<div ref={bottomRef} />
			</Box>
		</Box>
	);
}
