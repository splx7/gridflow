"use client";

import { useRef } from "react";
import { useProjectStore } from "@/stores/project-store";
import { uploadWeather, uploadLoadProfile } from "@/lib/api";

interface DataPanelProps {
  projectId: string;
}

export default function DataPanel({ projectId }: DataPanelProps) {
  const {
    weatherDatasets,
    loadProfiles,
    fetchPVGIS,
    fetchWeather,
    fetchLoadProfiles,
  } = useProjectStore();

  const weatherFileRef = useRef<HTMLInputElement>(null);
  const loadFileRef = useRef<HTMLInputElement>(null);

  const handleFetchPVGIS = async () => {
    await fetchPVGIS(projectId);
  };

  const handleUploadWeather = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await uploadWeather(projectId, file);
    await fetchWeather(projectId);
  };

  const handleUploadLoad = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await uploadLoadProfile(projectId, file);
    await fetchLoadProfiles(projectId);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Weather Data */}
      <section>
        <h3 className="text-lg font-semibold mb-4">Weather Data</h3>
        <div className="flex gap-3 mb-4">
          <button
            onClick={handleFetchPVGIS}
            className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          >
            Fetch from PVGIS
          </button>
          <button
            onClick={() => weatherFileRef.current?.click()}
            className="bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          >
            Upload TMY CSV
          </button>
          <input
            ref={weatherFileRef}
            type="file"
            accept=".csv"
            onChange={handleUploadWeather}
            className="hidden"
          />
        </div>

        {weatherDatasets.length === 0 ? (
          <p className="text-gray-500 text-sm">No weather datasets yet</p>
        ) : (
          <div className="space-y-2">
            {weatherDatasets.map((ds) => (
              <div
                key={ds.id}
                className="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center justify-between"
              >
                <div>
                  <span className="text-sm font-medium">{ds.name}</span>
                  <span className="text-xs text-gray-500 ml-2">({ds.source})</span>
                </div>
                <span className="text-xs text-gray-500">
                  {new Date(ds.created_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Load Profiles */}
      <section>
        <h3 className="text-lg font-semibold mb-4">Load Profiles</h3>
        <div className="flex gap-3 mb-4">
          <button
            onClick={() => loadFileRef.current?.click()}
            className="bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          >
            Upload Load CSV (8760 hourly kW)
          </button>
          <input
            ref={loadFileRef}
            type="file"
            accept=".csv"
            onChange={handleUploadLoad}
            className="hidden"
          />
        </div>

        {loadProfiles.length === 0 ? (
          <p className="text-gray-500 text-sm">No load profiles yet</p>
        ) : (
          <div className="space-y-2">
            {loadProfiles.map((lp) => (
              <div
                key={lp.id}
                className="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center justify-between"
              >
                <div>
                  <span className="text-sm font-medium">{lp.name}</span>
                  <span className="text-xs text-gray-500 ml-2">
                    ({lp.profile_type})
                  </span>
                </div>
                <span className="text-sm text-gray-400">
                  {(lp.annual_kwh / 1000).toFixed(0)} MWh/yr
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
