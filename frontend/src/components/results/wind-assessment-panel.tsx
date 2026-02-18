"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { getWindAssessment, getErrorMessage } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Wind } from "lucide-react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface WindAssessmentData {
  weibull_k: number;
  weibull_c: number;
  mean_wind_speed: number;
  max_wind_speed: number;
  aep_kwh: number;
  capacity_factor: number;
  hub_height_m: number;
  rated_power_kw: number;
  histogram: { bin_start: number; bin_end: number; hours: number }[];
  monthly_avg_wind_speed: number[];
}

interface Props {
  projectId: string;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function WindAssessmentPanel({ projectId }: Props) {
  const [data, setData] = useState<WindAssessmentData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getWindAssessment(projectId)
      .then((d) => setData(d as unknown as WindAssessmentData))
      .catch((err) => {
        const msg = getErrorMessage(err);
        if (!msg.includes("404")) toast.error("Wind assessment: " + msg);
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!data) {
    return (
      <Card variant="glass">
        <CardContent className="py-8 text-center text-muted-foreground">
          <Wind className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p>No wind data available. Fetch weather data first.</p>
        </CardContent>
      </Card>
    );
  }

  const histData = data.histogram.map((b) => ({
    range: `${b.bin_start}-${b.bin_end}`,
    hours: b.hours,
  }));

  const monthlyData = data.monthly_avg_wind_speed.map((v, i) => ({
    month: MONTHS[i],
    speed: v,
  }));

  return (
    <div className="space-y-6">
      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card variant="glass">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Weibull k</p>
            <p className="text-2xl font-bold mt-1">{data.weibull_k}</p>
            <p className="text-xs text-muted-foreground">Shape parameter</p>
          </CardContent>
        </Card>
        <Card variant="glass">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Weibull c</p>
            <p className="text-2xl font-bold mt-1">{data.weibull_c} m/s</p>
            <p className="text-xs text-muted-foreground">Scale parameter</p>
          </CardContent>
        </Card>
        <Card variant="glass">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Mean Speed</p>
            <p className="text-2xl font-bold mt-1">{data.mean_wind_speed} m/s</p>
            <p className="text-xs text-muted-foreground">At {data.hub_height_m}m hub</p>
          </CardContent>
        </Card>
        <Card variant="glass">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">AEP</p>
            <p className="text-2xl font-bold mt-1">
              {data.aep_kwh >= 1000
                ? `${(data.aep_kwh / 1000).toFixed(1)} MWh`
                : `${data.aep_kwh.toFixed(0)} kWh`}
            </p>
            <p className="text-xs text-muted-foreground">
              CF: {(data.capacity_factor * 100).toFixed(1)}%
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Wind Speed Histogram */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Wind Speed Distribution
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={histData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="range" tick={{ fontSize: 11 }} label={{ value: "m/s", position: "insideBottomRight", offset: -5 }} />
              <YAxis tick={{ fontSize: 11 }} label={{ value: "Hours", angle: -90, position: "insideLeft" }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                }}
              />
              <Bar dataKey="hours" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Monthly Wind Speeds */}
      {monthlyData.length > 0 && (
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Monthly Average Wind Speed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={monthlyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} unit=" m/s" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="speed"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  name="Avg Wind Speed (m/s)"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
