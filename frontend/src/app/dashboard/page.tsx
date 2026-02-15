"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { getErrorMessage } from "@/lib/api";
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
  Sun,
  Wind,
  Battery,
  MapPin,
  Plus,
  Trash2,
  Zap,
  FolderOpen,
} from "lucide-react";

const LocationPicker = dynamic(
  () => import("@/components/configure/location-picker"),
  { ssr: false }
);

export default function DashboardPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();
  const { projects, fetchProjects, createProject, deleteProject } =
    useProjectStore();

  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [latitude, setLatitude] = useState(0);
  const [longitude, setLongitude] = useState(0);
  const [description, setDescription] = useState("");

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchProjects().catch((err) => toast.error(getErrorMessage(err)));
    }
  }, [isAuthenticated, fetchProjects]);

  const handleCreate = async () => {
    if (!name) return;
    try {
      const project = await createProject({
        name,
        description: description || undefined,
        latitude,
        longitude,
      });
      setShowCreate(false);
      setName("");
      setDescription("");
      setLatitude(0);
      setLongitude(0);
      toast.success("Project created");
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
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Welcome + CTA */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-semibold">Projects</h2>
            <p className="text-muted-foreground text-sm mt-1">
              Design and simulate hybrid power systems
            </p>
          </div>
          <Button variant="gradient" onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" />
            New Project
          </Button>
        </div>

        {/* Create Project Dialog */}
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create New Project</DialogTitle>
              <DialogDescription>
                Set up a new power system simulation project. Choose a location
                on the map.
              </DialogDescription>
            </DialogHeader>

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
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={!name}>
                Create Project
              </Button>
            </DialogFooter>
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
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
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
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm("Delete this project?")) {
                          deleteProject(project.id)
                            .then(() => toast.success("Project deleted"))
                            .catch((err) => toast.error(getErrorMessage(err)));
                        }
                      }}
                      className="text-muted-foreground hover:text-destructive transition-colors ml-2 shrink-0"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
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
