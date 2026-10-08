"use client";

/**
 * Recharts wrappers. Colours come from the CSS custom properties so the charts
 * follow the light/dark theme instead of hard-coding a palette.
 */
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const axisStyle = { fontSize: 11, fill: "var(--muted)" };

const tooltipStyle = {
  contentStyle: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: 10,
    fontSize: 12,
    boxShadow: "var(--shadow-md)",
    color: "var(--foreground)",
  },
  labelStyle: { color: "var(--muted)", fontSize: 11, marginBottom: 4 },
  itemStyle: { color: "var(--foreground)" },
};

function shortDate(value: unknown) {
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value ?? "");
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function ActivityAreaChart({
  data,
}: {
  data: { date: string; issued: number; authentic: number; tampered: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
        <defs>
          {[
            ["gIssued", "var(--brand)"],
            ["gAuthentic", "var(--ok)"],
            ["gTampered", "var(--bad)"],
          ].map(([id, color]) => (
            <linearGradient key={id} id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={axisStyle} tickMargin={8} />
        <YAxis allowDecimals={false} tick={axisStyle} width={40} />
        <Tooltip {...tooltipStyle} labelFormatter={shortDate} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} iconType="circle" />
        <Area
          type="monotone"
          name="Issued"
          dataKey="issued"
          stroke="var(--brand)"
          fill="url(#gIssued)"
          strokeWidth={2}
        />
        <Area
          type="monotone"
          name="Authentic"
          dataKey="authentic"
          stroke="var(--ok)"
          fill="url(#gAuthentic)"
          strokeWidth={2}
        />
        <Area
          type="monotone"
          name="Tampered"
          dataKey="tampered"
          stroke="var(--bad)"
          fill="url(#gTampered)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

const RESULT_COLORS: Record<string, string> = {
  authentic: "var(--ok)",
  tampered: "var(--bad)",
  invalid: "var(--bad)",
  revoked: "var(--warn)",
  unknown: "var(--muted)",
};

export function VerdictPieChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).filter(([, value]) => value > 0);
  if (!entries.length) {
    return (
      <p className="grid h-[220px] place-items-center text-xs text-muted">
        No verifications recorded yet.
      </p>
    );
  }
  const chartData = entries.map(([name, value]) => ({ name, value }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={chartData}
          dataKey="value"
          nameKey="name"
          innerRadius={52}
          outerRadius={84}
          paddingAngle={2}
          stroke="var(--surface)"
          strokeWidth={2}
        >
          {chartData.map((entry) => (
            <Cell key={entry.name} fill={RESULT_COLORS[entry.name] ?? "var(--brand)"} />
          ))}
        </Pie>
        <Tooltip {...tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function FragmentBarChart({
  data,
}: {
  data: { label: string; value: number; tone: string }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis dataKey="label" tick={axisStyle} tickMargin={8} />
        <YAxis allowDecimals={false} tick={axisStyle} width={40} />
        <Tooltip {...tooltipStyle} />
        <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={56}>
          {data.map((entry) => (
            <Cell key={entry.label} fill={entry.tone} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TamperScoreGauge({ score }: { score: number }) {
  const tone =
    score === 0 ? "var(--ok)" : score < 35 ? "var(--warn)" : "var(--bad)";
  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={180}>
        <RadialBarChart
          data={[{ name: "score", value: score, fill: tone }]}
          innerRadius="70%"
          outerRadius="100%"
          startAngle={210}
          endAngle={-30}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar dataKey="value" cornerRadius={999} background={{ fill: "var(--neutral-soft)" }} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pt-4">
        <span className="text-3xl font-semibold tabular-nums" style={{ color: tone }}>
          {score}
        </span>
        <span className="text-[10px] uppercase tracking-wide text-muted">Tamper score</span>
      </div>
    </div>
  );
}

export function HotspotBarChart({
  data,
}: {
  data: { page_index: number; cell_index: number; hits: number }[];
}) {
  const chartData = data
    .slice(0, 10)
    .map((item) => ({ label: `p${item.page_index + 1}·c${item.cell_index}`, hits: item.hits }));
  if (!chartData.length) {
    return (
      <p className="grid h-[200px] place-items-center text-xs text-muted">
        No tampering recorded yet — nothing to rank.
      </p>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={chartData} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis dataKey="label" tick={axisStyle} tickMargin={8} />
        <YAxis allowDecimals={false} tick={axisStyle} width={40} />
        <Tooltip {...tooltipStyle} />
        <Bar dataKey="hits" fill="var(--bad)" radius={[6, 6, 0, 0]} maxBarSize={40} />
      </BarChart>
    </ResponsiveContainer>
  );
}
