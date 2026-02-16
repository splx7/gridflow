"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useProjectStore } from "@/stores/project-store";
import { getErrorMessage } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type {
  AdvisorRecommendation,
  GoalWeights,
  LoadProfile,
} from "@/types";
import LoadStep from "./load-step";
import GoalSelector, { ARCHETYPES } from "./goal-selector";
import RecommendationCard, { goalMatch } from "./recommendation-card";
import { ChevronLeft, Lightbulb } from "lucide-react";

const STEPS = ["Load Profile", "Goals", "Recommendations"] as const;

interface AdvisorWizardProps {
  projectId: string;
  onApplied: () => void; // called after components created → switch tab
}

export default function AdvisorWizard({
  projectId,
  onApplied,
}: AdvisorWizardProps) {
  const {
    loadProfiles,
    advisorResult,
    fetchRecommendations,
    addComponent,
    fetchComponents,
    fetchLoadProfiles,
    generateLoadProfile,
    setAppliedRecommendation,
  } = useProjectStore();

  const [step, setStep] = useState(0);

  // Step 1 state
  const [selectedLoadProfileId, setSelectedLoadProfileId] = useState<
    string | null
  >(null);
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [selectedCompositeScenarios, setSelectedCompositeScenarios] = useState<
    string[]
  >([]);
  const [annualKwhOverride, setAnnualKwhOverride] = useState<number | null>(
    null
  );
  const [peakKwOverride, setPeakKwOverride] = useState<number | null>(null);
  const [daytimeFractionOverride, setDaytimeFractionOverride] = useState<
    number | null
  >(null);

  // Step 2 state
  const [goals, setGoals] = useState<GoalWeights>({
    cost: 3,
    renewables: 3,
    reliability: 3,
    roi: 3,
  });
  const [gridAvailable, setGridAvailable] = useState(true);
  const [budgetCeiling, setBudgetCeiling] = useState<number | null>(null);
  const [activeArchetype, setActiveArchetype] = useState<string | null>(null);

  // Step 3 state
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState<number | null>(null);

  const isComposite = selectedCompositeScenarios.length > 0;

  const handleSelectLoadProfile = (id: string) => {
    setSelectedLoadProfileId(id);
    setSelectedScenario(null);
    setSelectedCompositeScenarios([]);
  };

  const handleSelectScenario = (key: string, _defaultKwh: number) => {
    setSelectedScenario(key);
    setSelectedLoadProfileId(null);
    setSelectedCompositeScenarios([]);
    setAnnualKwhOverride(null);
    setPeakKwOverride(null);
    setDaytimeFractionOverride(null);
  };

  const handleToggleCompositeScenario = (key: string) => {
    // Clear single-scenario selection when toggling composite
    setSelectedScenario(null);
    setSelectedLoadProfileId(null);
    setAnnualKwhOverride(null);
    setPeakKwOverride(null);
    setDaytimeFractionOverride(null);

    setSelectedCompositeScenarios((prev) =>
      prev.includes(key)
        ? prev.filter((k) => k !== key)
        : [...prev, key]
    );
  };

  const handleCsvUploaded = (profile: LoadProfile) => {
    // After upload, select the newly uploaded profile
    setSelectedLoadProfileId(profile.id);
    setSelectedScenario(null);
    setSelectedCompositeScenarios([]);
    fetchLoadProfiles(projectId);
  };

  const handleArchetypeSelect = (key: string) => {
    const arch = ARCHETYPES.find((a) => a.key === key);
    if (arch) {
      setGoals({ ...arch.goals });
      setActiveArchetype(key);
    }
  };

  const handleGetRecommendations = async () => {
    setLoading(true);
    try {
      // For composite scenarios, pass the first scenario key but override values
      const scenarioToSend = isComposite
        ? selectedCompositeScenarios[0]
        : selectedScenario;

      await fetchRecommendations(projectId, {
        load_profile_id: selectedLoadProfileId,
        scenario: scenarioToSend,
        annual_kwh: annualKwhOverride,
        peak_kw: peakKwOverride,
        daytime_fraction: daytimeFractionOverride,
        goals,
        grid_available: gridAvailable,
        budget_ceiling: budgetCeiling,
      });
      setStep(2);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async (rec: AdvisorRecommendation, index: number) => {
    setApplying(index);
    try {
      // 1. Create components
      for (const comp of rec.components) {
        await addComponent(projectId, {
          component_type: comp.component_type,
          name: comp.name,
          config: comp.config,
        });
      }

      // 2. Auto-generate load profile if using a scenario (not an existing profile)
      if (!selectedLoadProfileId) {
        try {
          if (isComposite && selectedCompositeScenarios.length > 1) {
            await generateLoadProfile(projectId, {
              scenarios: selectedCompositeScenarios,
              annual_kwh: annualKwhOverride ?? undefined,
            });
          } else if (isComposite && selectedCompositeScenarios.length === 1) {
            await generateLoadProfile(projectId, {
              scenario: selectedCompositeScenarios[0],
              annual_kwh: annualKwhOverride ?? undefined,
            });
          } else if (selectedScenario) {
            await generateLoadProfile(projectId, {
              scenario: selectedScenario,
              annual_kwh: annualKwhOverride ?? undefined,
            });
          }
          await fetchLoadProfiles(projectId);
        } catch {
          // Load profile generation is best-effort; don't block component apply
          toast.error("Components created but load profile generation failed");
        }
      }

      setAppliedRecommendation(rec);
      toast.success(
        `Applied "${rec.name}" — ${rec.components.length} components created`
      );
      await fetchComponents(projectId);
      onApplied();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setApplying(null);
    }
  };

  // Find best recommendation for current goals
  const findRecommended = (recs: AdvisorRecommendation[]): number => {
    let bestIdx = 0;
    let bestScore = -1;
    recs.forEach((r, i) => {
      const score = goalMatch(r, goals);
      if (score > bestScore) {
        bestScore = score;
        bestIdx = i;
      }
    });
    return bestIdx;
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
          <Lightbulb className="h-4 w-4 text-white" />
        </div>
        <div>
          <h3 className="text-lg font-semibold">System Advisor</h3>
          <p className="text-xs text-muted-foreground">
            Get personalized system recommendations based on your load and goals
          </p>
        </div>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            {i > 0 && (
              <div
                className={`h-px w-8 ${
                  i <= step ? "bg-primary" : "bg-border"
                }`}
              />
            )}
            <div className="flex items-center gap-1.5">
              <div
                className={`h-6 w-6 rounded-full flex items-center justify-center text-xs font-medium ${
                  i < step
                    ? "bg-primary text-primary-foreground"
                    : i === step
                    ? "bg-primary/20 text-primary border border-primary"
                    : "bg-secondary text-muted-foreground"
                }`}
              >
                {i + 1}
              </div>
              <span
                className={`text-sm ${
                  i === step ? "font-medium" : "text-muted-foreground"
                }`}
              >
                {label}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Step content */}
      {step === 0 && (
        <LoadStep
          loadProfiles={loadProfiles}
          selectedLoadProfileId={selectedLoadProfileId}
          selectedScenario={selectedScenario}
          selectedCompositeScenarios={selectedCompositeScenarios}
          annualKwhOverride={annualKwhOverride}
          peakKwOverride={peakKwOverride}
          daytimeFractionOverride={daytimeFractionOverride}
          onSelectLoadProfile={handleSelectLoadProfile}
          onSelectScenario={handleSelectScenario}
          onToggleCompositeScenario={handleToggleCompositeScenario}
          onAnnualKwhChange={setAnnualKwhOverride}
          onPeakKwChange={setPeakKwOverride}
          onDaytimeFractionChange={setDaytimeFractionOverride}
          onCsvUploaded={handleCsvUploaded}
          onNext={() => setStep(1)}
          projectId={projectId}
        />
      )}

      {step === 1 && (
        <GoalSelector
          goals={goals}
          gridAvailable={gridAvailable}
          budgetCeiling={budgetCeiling}
          activeArchetype={activeArchetype}
          onGoalsChange={(g) => {
            setGoals(g);
            setActiveArchetype(null);
          }}
          onGridChange={setGridAvailable}
          onBudgetChange={setBudgetCeiling}
          onArchetypeSelect={handleArchetypeSelect}
          onBack={() => setStep(0)}
          onNext={handleGetRecommendations}
        />
      )}

      {step === 2 && (
        <div className="space-y-4">
          {loading ? (
            <Card variant="glass">
              <CardContent className="py-12 text-center">
                <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">
                  Analyzing your load profile and generating recommendations...
                </p>
              </CardContent>
            </Card>
          ) : advisorResult ? (
            <>
              {/* Load & solar summary */}
              <div className="flex flex-wrap gap-3 text-xs">
                <Badge variant="secondary">
                  {advisorResult.load_summary.annual_kwh.toLocaleString()}{" "}
                  kWh/yr
                </Badge>
                <Badge variant="secondary">
                  Peak: {advisorResult.load_summary.peak_kw.toFixed(1)} kW
                </Badge>
                <Badge variant="secondary">
                  PSH: {advisorResult.solar_resource.peak_sun_hours.toFixed(1)}{" "}
                  h/day
                </Badge>
                <Badge variant="secondary">
                  CF: {(advisorResult.solar_resource.estimated_cf * 100).toFixed(1)}%
                </Badge>
              </div>

              {/* Recommendation cards */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {advisorResult.recommendations.map((rec, i) => (
                  <RecommendationCard
                    key={i}
                    recommendation={rec}
                    isRecommended={
                      i === findRecommended(advisorResult.recommendations)
                    }
                    goals={goals}
                    applying={applying === i}
                    onApply={() => handleApply(rec, i)}
                    applyLabel="Apply & Continue to Configure"
                  />
                ))}
              </div>

              {/* Back button */}
              <div className="flex justify-start pt-2">
                <Button variant="ghost" onClick={() => setStep(1)}>
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Adjust Goals
                </Button>
              </div>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
