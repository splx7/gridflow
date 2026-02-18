"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  listAnnotations,
  createAnnotation,
  updateAnnotation,
  deleteAnnotation,
  getErrorMessage,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Plus, Pencil, Trash2, StickyNote, AlertCircle, CheckCircle2 } from "lucide-react";

interface Annotation {
  id: string;
  text: string;
  annotation_type: "note" | "decision" | "issue";
  created_at: string;
  updated_at: string;
}

interface Props {
  projectId: string;
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
  note: <StickyNote className="h-3.5 w-3.5" />,
  decision: <CheckCircle2 className="h-3.5 w-3.5" />,
  issue: <AlertCircle className="h-3.5 w-3.5" />,
};

const TYPE_COLORS: Record<string, string> = {
  note: "bg-blue-500/20 text-blue-400",
  decision: "bg-emerald-500/20 text-emerald-400",
  issue: "bg-amber-500/20 text-amber-400",
};

export default function AnnotationsPanel({ projectId }: Props) {
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [loading, setLoading] = useState(true);
  const [newText, setNewText] = useState("");
  const [newType, setNewType] = useState<"note" | "decision" | "issue">("note");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");

  const fetchAnnotations = async () => {
    try {
      const data = await listAnnotations(projectId);
      setAnnotations(data as unknown as Annotation[]);
    } catch (err) {
      const msg = getErrorMessage(err);
      if (!msg.includes("404")) toast.error("Failed to load notes: " + msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnnotations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const handleCreate = async () => {
    if (!newText.trim()) return;
    try {
      await createAnnotation(projectId, { text: newText, annotation_type: newType });
      setNewText("");
      await fetchAnnotations();
    } catch (err) {
      toast.error("Failed to create note: " + getErrorMessage(err));
    }
  };

  const handleUpdate = async (id: string) => {
    if (!editText.trim()) return;
    try {
      await updateAnnotation(projectId, id, { text: editText });
      setEditingId(null);
      await fetchAnnotations();
    } catch (err) {
      toast.error("Failed to update note: " + getErrorMessage(err));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteAnnotation(projectId, id);
      await fetchAnnotations();
    } catch (err) {
      toast.error("Failed to delete note: " + getErrorMessage(err));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Add new note */}
      <Card variant="glass">
        <CardContent className="pt-4 pb-4">
          <div className="flex gap-2 mb-2">
            {(["note", "decision", "issue"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setNewType(t)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors flex items-center gap-1 ${
                  newType === t ? TYPE_COLORS[t] : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                {TYPE_ICONS[t]}
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <textarea
              value={newText}
              onChange={(e) => setNewText(e.target.value)}
              placeholder="Add a note, decision, or issue..."
              className="flex-1 bg-background/50 border border-border rounded-lg px-3 py-2 text-sm resize-none min-h-[60px]"
              rows={2}
            />
            <Button onClick={handleCreate} disabled={!newText.trim()} size="sm" className="self-end">
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Annotations list */}
      {annotations.length === 0 ? (
        <p className="text-center text-muted-foreground text-sm py-4">No notes yet.</p>
      ) : (
        <div className="space-y-2">
          {annotations.map((a) => (
            <Card key={a.id} variant="glass">
              <CardContent className="pt-3 pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge className={`text-xs ${TYPE_COLORS[a.annotation_type]}`}>
                        {TYPE_ICONS[a.annotation_type]}
                        <span className="ml-1">{a.annotation_type}</span>
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {new Date(a.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    {editingId === a.id ? (
                      <div className="flex gap-2 mt-1">
                        <textarea
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          className="flex-1 bg-background/50 border border-border rounded-lg px-3 py-2 text-sm resize-none"
                          rows={2}
                        />
                        <div className="flex flex-col gap-1">
                          <Button size="sm" onClick={() => handleUpdate(a.id)}>Save</Button>
                          <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>Cancel</Button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm whitespace-pre-wrap">{a.text}</p>
                    )}
                  </div>
                  {editingId !== a.id && (
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0"
                        onClick={() => { setEditingId(a.id); setEditText(a.text); }}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                        onClick={() => handleDelete(a.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
