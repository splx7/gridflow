"use client";

import { useEffect, useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, checkAuth, logout } = useAuthStore();
  const { projects, fetchProjects, createProject, deleteProject } = useProjectStore();

  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [latitude, setLatitude] = useState("0");
  const [longitude, setLongitude] = useState("0");
  const [description, setDescription] = useState("");

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchProjects();
    }
  }, [isAuthenticated, fetchProjects]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    const project = await createProject({
      name,
      description: description || undefined,
      latitude: parseFloat(latitude),
      longitude: parseFloat(longitude),
    });
    setShowCreate(false);
    setName("");
    setDescription("");
    router.push(`/projects/${project.id}`);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-blue-400">GridFlow</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-400">{user?.email}</span>
            <button
              onClick={logout}
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-2xl font-semibold">Projects</h2>
          <button
            onClick={() => setShowCreate(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          >
            New Project
          </button>
        </div>

        {/* Create Project Modal */}
        {showCreate && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
            <form
              onSubmit={handleCreate}
              className="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-lg space-y-4"
            >
              <h3 className="text-lg font-semibold">Create New Project</h3>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Project Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Description</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={2}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Latitude</label>
                  <input
                    type="number"
                    step="any"
                    value={latitude}
                    onChange={(e) => setLatitude(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Longitude</label>
                  <input
                    type="number"
                    step="any"
                    value={longitude}
                    onChange={(e) => setLongitude(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
              </div>

              <div className="flex gap-3 justify-end">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Project Grid */}
        {projects.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <p className="text-lg">No projects yet</p>
            <p className="text-sm mt-1">Create your first project to get started</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
              <div
                key={project.id}
                onClick={() => router.push(`/projects/${project.id}`)}
                className="bg-gray-900 border border-gray-800 rounded-xl p-5 cursor-pointer hover:border-gray-700 transition-colors group"
              >
                <div className="flex items-start justify-between">
                  <h3 className="font-semibold group-hover:text-blue-400 transition-colors">
                    {project.name}
                  </h3>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm("Delete this project?")) {
                        deleteProject(project.id);
                      }
                    }}
                    className="text-gray-600 hover:text-red-400 text-sm transition-colors"
                  >
                    Delete
                  </button>
                </div>
                {project.description && (
                  <p className="text-sm text-gray-400 mt-1 line-clamp-2">
                    {project.description}
                  </p>
                )}
                <div className="flex gap-4 mt-3 text-xs text-gray-500">
                  <span>
                    {project.latitude.toFixed(2)}, {project.longitude.toFixed(2)}
                  </span>
                  <span>{project.lifetime_years}yr</span>
                  <span>{(project.discount_rate * 100).toFixed(0)}% DR</span>
                </div>
                <p className="text-xs text-gray-600 mt-2">
                  Updated {new Date(project.updated_at).toLocaleDateString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
