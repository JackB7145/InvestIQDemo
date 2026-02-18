export const toolsResponse = [
	{
		type: "LineGraph",
		data: {
			title: "Sample Line Graph",
			data: [
				{ name: "Jan", sales: 30, profit: 20 },
				{ name: "Feb", sales: 45, profit: 25 },
				{ name: "Mar", sales: 60, profit: 35 },
			],
			series: [
				{ key: "sales", color: "#1976d2" },
				{ key: "profit", color: "#ff5722" },
			],
		},
	},
	{
		type: "BarGraph",
		data: {
			title: "Sample Bar Graph",
			data: [
				{ name: "Product A", qty: 40 },
				{ name: "Product B", qty: 55 },
				{ name: "Product C", qty: 30 },
			],
			series: [{ key: "qty", color: "#4caf50" }],
		},
	},
	{
		type: "ScatterPlot",
		data: {
			title: "Sample Scatter Plot",
			data: [
				{ x: 5, y: 20 },
				{ x: 10, y: 35 },
				{ x: 15, y: 40 },
				{ x: 20, y: 25 },
			],
			series: [{ xKey: "x", yKey: "y", color: "#9c27b0" }],
		},
	},
];
