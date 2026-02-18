"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { getErrorMessage, exportProject, importProject } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sun,
  Wind,
  Battery,
  MapPin,
  Plus,
  Trash2,
  Zap,
  FolderOpen,
  LogOut,
  LogIn,
  Search,
  Copy,
  Download,
  Upload,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import TemplatePicker from "@/components/dashboard/template-picker";
import type { ProjectTemplate } from "@/types";

const LocationPicker = dynamic(
  () => import("@/components/configure/location-picker"),
  { ssr: false }
);

type SortOption = "updated" | "name" | "created";

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, checkAuth, logout } = useAuthStore();
  const { projects, fetchProjects, createProject, deleteProject, duplicateProject, fetchPVGIS } =
    useProjectStore();
  const importFileRef = useRef<HTMLInputElement>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [createStep, setCreateStep] = useState<"template" | "form">("template");
  const [name, setName] = useState("");
  const [latitude, setLatitude] = useState(0);
  const [longitude, setLongitude] = useState(0);
  const [description, setDescription] = useState("");
  const [pendingTemplate, setPendingTemplate] = useState<ProjectTemplate | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortOption>("updated");

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchProjects().catch((err) => toast.error(getErrorMessage(err)));
    }
  }, [isAuthenticated, fetchProjects]);

  const filteredProjects = useMemo(() => {
    let filtered = projects;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.description?.toLowerCase().includes(q) ||
          `${p.latitude.toFixed(2)}, ${p.longitude.toFixed(2)}`.includes(q)
      );
    }

    const sorted = [...filtered];
    switch (sortBy) {
      case "name":
        sorted.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case "created":
        sorted.sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        break;
      case "updated":
      default:
        sorted.sort(
          (a, b) =>
            new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        );
        break;
    }

    return sorted;
  }, [projects, searchQuery, sortBy]);

  const handleTemplateSelect = (template: ProjectTemplate) => {
    setPendingTemplate(template);
    setName(template.name);
    setDescription(template.description);
    setLatitude(template.project.latitude);
    setLongitude(template.project.longitude);
    setCreateStep("form");
  };

  const handleCreate = async () => {
    if (!name) return;
    try {
      const project = await createProject({
        name,
        description: description || undefined,
        latitude,
        longitude,
        lifetime_years: pendingTemplate?.project.lifetime_years,
        discount_rate: pendingTemplate?.project.discount_rate,
      });

      // If from template, add components
      if (pendingTemplate?.components) {
        const { createComponent } = await import("@/lib/api");
        for (const comp of pendingTemplate.components) {
          await createComponent(project.id, {
            component_type: comp.component_type,
            name: comp.name,
            config: comp.config,
          });
        }
        // Generate load profile from template
        if (pendingTemplate.load) {
          const { generateLoadProfile } = await import("@/lib/api");
          await generateLoadProfile(project.id, {
            scenario: pendingTemplate.load.scenario,
            annual_kwh: pendingTemplate.load.annual_kwh,
          }).catch(() => {});
        }
      }

      setShowCreate(false);
      setCreateStep("template");
      setName("");
      setDescription("");
      setLatitude(0);
      setLongitude(0);
      setPendingTemplate(null);
      toast.success("Project created");
      // Auto-fetch PVGIS weather data in background
      fetchPVGIS(project.id).catch(() => {
        // Silently ignore — project page will retry if needed
      });
      router.push(`/projects/${project.id}`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border bg-background/80 backdrop-blur-lg sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <h1 className="text-xl font-bold gradient-text">GridFlow</h1>
          </div>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            {user && !user.email.endsWith("@gridflow.local") ? (
              <>
                <span className="text-sm text-muted-foreground">{user.email}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    logout();
                    router.push("/");
                  }}
                >
                  <LogOut className="h-4 w-4 mr-1" />
                  Log out
                </Button>
              </>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push("/")}
              >
                <LogIn className="h-4 w-4 mr-1" />
                Sign In
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Welcome + CTA */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold">Projects</h2>
            <p className="text-muted-foreground text-sm mt-1">
              Design and simulate hybrid power systems
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              ref={importFileRef}
              type="file"
              accept=".json"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                  const text = await file.text();
                  const bundle = JSON.parse(text);
                  const project = await importProject(bundle);
                  await fetchProjects();
                  toast.success(`Imported "${project.name}"`);
                  router.push(`/projects/${project.id}`);
                } catch (err) {
                  toast.error(getErrorMessage(err));
                }
                e.target.value = "";
              }}
            />
            <Button variant="outline" onClick={() => importFileRef.current?.click()}>
              <Upload className="h-4 w-4" />
              Import
            </Button>
            <Button variant="gradient" onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4" />
              New Project
            </Button>
          </div>
        </div>

        {/* Search & Sort */}
        {projects.length > 0 && (
          <div className="flex items-center gap-3 mb-6">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search projects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortOption)}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Sort by..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="updated">Last Updated</SelectItem>
                <SelectItem value="name">Name (A-Z)</SelectItem>
                <SelectItem value="created">Date Created</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Create Project Dialog */}
        <Dialog open={showCreate} onOpenChange={(open) => {
          setShowCreate(open);
          if (!open) {
            setCreateStep("template");
            setPendingTemplate(null);
            setName("");
            setDescription("");
            setLatitude(0);
            setLongitude(0);
          }
        }}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create New Project</DialogTitle>
              <DialogDescription>
                {createStep === "template"
                  ? "Choose a template or start with a blank project."
                  : "Set up your project details and location."}
              </DialogDescription>
            </DialogHeader>

            {createStep === "template" ? (
              <TemplatePicker
                onSelect={handleTemplateSelect}
                onSkip={() => setCreateStep("form")}
              />
            ) : (
              <>
                <div className="space-y-4">
                  <div>
                    <Label>Project Name</Label>
                    <Input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g. Nairobi Solar + Battery"
                    />
                  </div>

                  <div>
                    <Label>Description</Label>
                    <Input
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Optional project description"
                    />
                  </div>

                  <div>
                    <Label>Location</Label>
                    <LocationPicker
                      latitude={latitude}
                      longitude={longitude}
                      onChange={(lat, lng) => {
                        setLatitude(lat);
                        setLongitude(lng);
                      }}
                    />
                  </div>
                </div>

                <DialogFooter>
                  <Button variant="ghost" onClick={() => {
                    setCreateStep("template");
                    setPendingTemplate(null);
                  }}>
                    Back
                  </Button>
                  <Button onClick={handleCreate} disabled={!name}>
                    {pendingTemplate ? "Create from Template" : "Create Project"}
                  </Button>
                </DialogFooter>
              </>
            )}
          </DialogContent>
        </Dialog>

        {/* Project Grid */}
        {projects.length === 0 ? (
          <Card variant="glass" className="card-lift">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <div className="h-16 w-16 rounded-2xl bg-muted flex items-center justify-center mb-4">
                <FolderOpen className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold mb-1">No projects yet</h3>
              <p className="text-muted-foreground text-sm mb-6">
                Create your first project to start designing power systems
              </p>
              <Button variant="gradient" onClick={() => setShowCreate(true)}>
                <Plus className="h-4 w-4" />
                Create First Project
              </Button>
            </CardContent>
          </Card>
        ) : filteredProjects.length === 0 ? (
          <Card variant="glass">
            <CardContent className="py-12 text-center">
              <Search className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground text-sm">
                No projects match &quot;{searchQuery}&quot;
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredProjects.map((project) => (
              <Card
                key={project.id}
                variant="glass"
                className="card-lift cursor-pointer group"
                onClick={() => router.push(`/projects/${project.id}`)}
              >
                <CardContent className="p-5">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold group-hover:text-primary transition-colors truncate">
                        {project.name}
                      </h3>
                      {project.description && (
                        <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                          {project.description}
                        </p>
                      )}
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button
                          onClick={(e) => e.stopPropagation()}
                          className="text-muted-foreground hover:text-foreground transition-colors ml-2 shrink-0 p-1 rounded"
                        >
                          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                            <circle cx="12" cy="5" r="2" />
                            <circle cx="12" cy="12" r="2" />
                            <circle cx="12" cy="19" r="2" />
                          </svg>
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                        <DropdownMenuItem
                          onClick={async () => {
                            try {
                              const dup = await duplicateProject(project.id);
                              toast.success(`Duplicated as "${dup.name}"`);
                            } catch (err) {
                              toast.error(getErrorMessage(err));
                            }
                          }}
                        >
                          <Copy className="h-4 w-4 mr-2" />
                          Duplicate
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={async () => {
                            try {
                              const bundle = await exportProject(project.id);
                              const blob = new Blob([JSON.stringify(bundle, null, 2)], {
                                type: "application/json",
                              });
                              const url = URL.createObjectURL(blob);
                              const a = document.createElement("a");
                              a.href = url;
                              a.download = `${project.name.replace(/\s+/g, "_")}.json`;
                              a.click();
                              URL.revokeObjectURL(url);
                            } catch (err) {
                              toast.error(getErrorMessage(err));
                            }
                          }}
                        >
                          <Download className="h-4 w-4 mr-2" />
                          Export JSON
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => {
                            if (confirm("Delete this project?")) {
                              deleteProject(project.id)
                                .then(() => toast.success("Project deleted"))
                                .catch((err) => toast.error(getErrorMessage(err)));
                            }
                          }}
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>

                  <div className="flex items-center gap-1.5 mt-3 text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3" />
                    <span>
                      {project.latitude.toFixed(2)},{" "}
                      {project.longitude.toFixed(2)}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 mt-3">
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Sun className="h-3 w-3 text-amber-400" />
                      <Wind className="h-3 w-3 text-sky-400" />
                      <Battery className="h-3 w-3 text-emerald-400" />
                    </div>
                    <div className="flex-1" />
                    <span className="text-xs text-muted-foreground">
                      {project.lifetime_years}yr &middot;{" "}
                      {(project.discount_rate * 100).toFixed(0)}% DR
                    </span>
                  </div>

                  <p className="text-xs text-muted-foreground/60 mt-2">
                    Updated{" "}
                    {new Date(project.updated_at).toLocaleDateString()}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
