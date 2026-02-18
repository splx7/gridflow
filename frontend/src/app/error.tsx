"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  const isNetworkError =
    error.message?.includes("fetch") ||
    error.message?.includes("network") ||
    error.message?.includes("ECONNREFUSED");

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4 px-4 max-w-md">
        <div className="h-16 w-16 rounded-2xl bg-destructive/10 flex items-center justify-center mx-auto">
          <AlertTriangle className="h-8 w-8 text-destructive" />
        </div>
        <h2 className="text-xl font-semibold">
          {isNetworkError ? "Connection Error" : "Something went wrong"}
        </h2>
        <p className="text-muted-foreground text-sm">
          {isNetworkError
            ? "Unable to connect to the server. Please check that the backend is running and try again."
            : error.message || "An unexpected error occurred. Please try again."}
        </p>
        {error.digest && (
          <p className="text-xs text-muted-foreground/60 font-mono">
            Error ID: {error.digest}
          </p>
        )}
        <div className="flex gap-3 justify-center pt-2">
          <button
            onClick={reset}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Try Again
          </button>
          <a
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-accent transition-colors gap-2"
          >
            <Home className="h-4 w-4" />
            Dashboard
          </a>
        </div>
      </div>
    </div>
  );
}
