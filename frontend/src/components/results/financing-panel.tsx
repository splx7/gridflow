"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { getFinancingAnalysis, getErrorMessage } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, DollarSign } from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

interface FinancingResult {
  wacc: number;
  debt_amount: number;
  equity_amount: number;
  breakeven_year: number | null;
  total_debt_service: number;
  total_interest: number;
  annual_revenue: number;
  lifetime_years: number;
  loan_schedule: { year: number; payment: number; principal_payment: number; interest_payment: number; remaining_balance: number }[];
  yearly_cashflows: {
    year: number;
    net_cashflow: number;
    cumulative_nominal: number;
    cumulative_discounted: number;
    om_cost: number;
    fuel_cost: number;
    loan_payment: number;
    revenue: number;
  }[];
}

interface Props {
  simulationId: string;
}

const fmt = (v: number) =>
  v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `$${(v / 1e3).toFixed(1)}k` : `$${v.toFixed(0)}`;

export default function FinancingPanel({ simulationId }: Props) {
  const [data, setData] = useState<FinancingResult | null>(null);
  const [loading, setLoading] = useState(false);

  // Financing params
  const [debtFraction, setDebtFraction] = useState(0.7);
  const [interestRate, setInterestRate] = useState(0.06);
  const [loanTerm, setLoanTerm] = useState(10);
  const [equityCost, setEquityCost] = useState(0.12);
  const [taxRate, setTaxRate] = useState(0.0);
  const [omEscalation, setOmEscalation] = useState(0.02);

  const runAnalysis = async () => {
    setLoading(true);
    try {
      const result = await getFinancingAnalysis(simulationId, {
        debt_fraction: debtFraction,
        interest_rate: interestRate,
        loan_term: loanTerm,
        equity_cost: equityCost,
        tax_rate: taxRate,
        om_escalation: omEscalation,
      });
      setData(result as unknown as FinancingResult);
    } catch (err) {
      toast.error("Financing analysis failed: " + getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runAnalysis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simulationId]);

  const cashflowData = data?.yearly_cashflows.map((cf) => ({
    year: cf.year,
    cumulative: cf.cumulative_discounted,
    net: cf.net_cashflow,
  })) ?? [];

  const loanData = data?.loan_schedule.map((ls) => ({
    year: ls.year,
    principal: ls.principal_payment,
    interest: ls.interest_payment,
  })) ?? [];

  return (
    <div className="space-y-6">
      {/* Parameter Inputs */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Financing Parameters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="space-y-1">
              <Label className="text-xs">Debt Fraction</Label>
              <Input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={debtFraction}
                onChange={(e) => setDebtFraction(Number(e.target.value))}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Interest Rate</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={interestRate}
                onChange={(e) => setInterestRate(Number(e.target.value))}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Loan Term (yr)</Label>
              <Input
                type="number"
                step="1"
                min="1"
                max="30"
                value={loanTerm}
                onChange={(e) => setLoanTerm(Number(e.target.value))}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Equity Cost</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={equityCost}
                onChange={(e) => setEquityCost(Number(e.target.value))}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Tax Rate</Label>
              <Input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={taxRate}
                onChange={(e) => setTaxRate(Number(e.target.value))}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">O&M Escalation</Label>
              <Input
                type="number"
                step="0.005"
                min="0"
                max="0.2"
                value={omEscalation}
                onChange={(e) => setOmEscalation(Number(e.target.value))}
              />
            </div>
          </div>
          <Button onClick={runAnalysis} disabled={loading} className="mt-4" size="sm">
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <DollarSign className="h-4 w-4 mr-1.5" />}
            {loading ? "Calculating..." : "Update Analysis"}
          </Button>
        </CardContent>
      </Card>

      {data && (
        <>
          {/* Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card variant="glass">
              <CardContent className="pt-4 pb-4">
                <p className="text-xs text-muted-foreground uppercase tracking-wider">WACC</p>
                <p className="text-2xl font-bold mt-1">{(data.wacc * 100).toFixed(2)}%</p>
              </CardContent>
            </Card>
            <Card variant="glass">
              <CardContent className="pt-4 pb-4">
                <p className="text-xs text-muted-foreground uppercase tracking-wider">Breakeven</p>
                <p className="text-2xl font-bold mt-1">
                  {data.breakeven_year ? `Year ${data.breakeven_year}` : "N/A"}
                </p>
              </CardContent>
            </Card>
            <Card variant="glass">
              <CardContent className="pt-4 pb-4">
                <p className="text-xs text-muted-foreground uppercase tracking-wider">Total Interest</p>
                <p className="text-2xl font-bold mt-1">{fmt(data.total_interest)}</p>
              </CardContent>
            </Card>
            <Card variant="glass">
              <CardContent className="pt-4 pb-4">
                <p className="text-xs text-muted-foreground uppercase tracking-wider">Annual Revenue</p>
                <p className="text-2xl font-bold mt-1">{fmt(data.annual_revenue)}</p>
              </CardContent>
            </Card>
          </div>

          {/* Cumulative Cashflow Chart */}
          <Card variant="glass">
            <CardHeader>
              <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Cumulative Discounted Cashflow
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={cashflowData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="year" tick={{ fontSize: 11 }} label={{ value: "Year", position: "insideBottomRight", offset: -5 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px" }}
                    formatter={(value: number) => [`$${value.toLocaleString()}`, "Cumulative"]}
                  />
                  <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
                  <Area
                    type="monotone"
                    dataKey="cumulative"
                    stroke="hsl(var(--primary))"
                    fill="hsl(var(--primary))"
                    fillOpacity={0.2}
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Loan Amortization */}
          {loanData.length > 0 && (
            <Card variant="glass">
              <CardHeader>
                <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  Loan Amortization
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={loanData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px" }}
                    />
                    <Bar dataKey="principal" stackId="a" fill="hsl(var(--primary))" name="Principal" radius={[0, 0, 0, 0]} />
                    <Bar dataKey="interest" stackId="a" fill="hsl(var(--destructive))" name="Interest" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
