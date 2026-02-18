"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MapPin, Sun, Battery, Zap, Wind, Loader2 } from "lucide-react";
import { listProjectTemplates, getProjectTemplate } from "@/lib/api";
import type { ProjectTemplateSummary, ProjectTemplate } from "@/types";

interface TemplatePickerProps {
  onSelect: (template: ProjectTemplate) => void;
  onSkip: () => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  "off-grid": "bg-amber-500/10 text-amber-500",
  "grid-connected": "bg-blue-500/10 text-blue-500",
  general: "bg-gray-500/10 text-gray-500",
};

const ICONS: Record<string, React.ReactNode> = {
  solar_pv: <Sun className="h-3 w-3 text-amber-400" />,
  battery: <Battery className="h-3 w-3 text-emerald-400" />,
  diesel_generator: <Zap className="h-3 w-3 text-purple-400" />,
  wind_turbine: <Wind className="h-3 w-3 text-sky-400" />,
  grid_connection: <Zap className="h-3 w-3 text-indigo-400" />,
};

export default function TemplatePicker({ onSelect, onSkip }: TemplatePickerProps) {
  const [templates, setTemplates] = useState<ProjectTemplateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState<string | null>(null);

  useEffect(() => {
    listProjectTemplates()
      .then(setTemplates)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSelect = async (id: string) => {
    setSelecting(id);
    try {
      const template = await getProjectTemplate(id);
      onSelect(template);
    } catch {
      setSelecting(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (templates.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">Start from a Template</p>
          <p className="text-xs text-muted-foreground">
            Pre-configured project with components and load profile
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onSkip}>
          Blank Project
        </Button>
      </div>
      <div className="grid grid-cols-1 gap-3">
        {templates.map((t) => (
          <Card
            key={t.id}
            variant="glass"
            className="cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => handleSelect(t.id)}
          >
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-medium">{t.name}</h4>
                    <Badge
                      variant="secondary"
                      className={`text-[10px] ${CATEGORY_COLORS[t.category] || ""}`}
                    >
                      {t.category}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                    {t.description}
                  </p>
                  <div className="flex items-center gap-3 mt-2">
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <MapPin className="h-3 w-3" />
                      {t.location.latitude.toFixed(1)}, {t.location.longitude.toFixed(1)}
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {t.component_count} components
                    </span>
                  </div>
                </div>
                {selecting === t.id && (
                  <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
