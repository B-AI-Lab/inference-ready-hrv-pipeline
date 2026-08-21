import { Line, LineChart, ResponsiveContainer } from "recharts";

export function Sparkline<T extends object>({ data, dataKey, color = "#c084fc" }: { data: T[]; dataKey: keyof T & string; color?: string }) {
  return (
    <div className="h-12 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data.slice(-50)}>
          <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
