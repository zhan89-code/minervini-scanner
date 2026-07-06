// components/PriceChart.tsx (CODE_BLUEPRINT.md §4/§6) -- candlestick series
// + volume histogram, via lightweight-charts. Annotates the VCP pivot line
// and each detected base leg (peak/trough markers) when vcp flagged (§4.4).
import {
  createChart,
  createSeriesMarkers,
  ColorType,
  CandlestickSeries,
  HistogramSeries,
  type IChartApi,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { PricePoint, VcpLeg } from "../api";

interface Props {
  prices: PricePoint[];
  pivot?: number | null;
  legs?: VcpLeg[] | null;
}

export default function PriceChart({ prices, pivot, legs }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      height: 340,
      layout: { background: { type: ColorType.Solid, color: "transparent" } },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
    });
    chartRef.current = chart;

    const bars = prices.filter(
      (p) => p.o !== null && p.h !== null && p.l !== null && p.c !== null
    );

    const candles = chart.addSeries(CandlestickSeries, {
      priceScaleId: "right",
    });
    candles.setData(
      bars.map((p) => ({
        time: p.date, open: p.o as number, high: p.h as number,
        low: p.l as number, close: p.c as number,
      }))
    );

    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    volume.setData(
      prices
        .filter((p) => p.v !== null)
        .map((p) => ({ time: p.date, value: p.v as number }))
    );

    if (pivot) {
      candles.createPriceLine({ price: pivot, color: "#cf222e", lineStyle: 2, title: "pivot" });
    }

    if (legs && legs.length > 0) {
      const markers = legs.flatMap((leg: VcpLeg) => [
        { time: leg.start, position: "aboveBar" as const, color: "#1a7f37", shape: "arrowDown" as const, text: `peak ${leg.hi.toFixed(2)}` },
        { time: leg.end, position: "belowBar" as const, color: "#cf222e", shape: "arrowUp" as const, text: `${leg.depth_pct.toFixed(0)}% leg` },
      ]);
      createSeriesMarkers(candles, markers);
    }

    chart.timeScale().fitContent();

    const resize = () => chart.applyOptions({ width: containerRef.current!.clientWidth });
    resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
    };
  }, [prices, pivot, legs]);

  return <div ref={containerRef} style={{ width: "100%" }} />;
}
