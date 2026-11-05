import React from "react";
import { LoaderCircle, AlertCircle } from "lucide-react";
import "molstar/build/viewer/molstar.css";
import { useTMText } from "#/i18n/targetmind-strings";

/** File extensions we render with the Mol* 3D structure viewer. */
export const MOLECULE_EXTS = new Set([
  "pdb",
  "sdf",
  "mol2",
  "mol",
  "xyz",
  "cif",
  "mmcif",
  "pdbqt",
  "gro",
]);

/** Map a file extension to a Mol* BuiltInTrajectoryFormat id. */
function molFormat(ext: string): string {
  if (ext === "cif" || ext === "mmcif") return "mmcif";
  return ext; // pdb, sdf, mol2, mol, xyz, pdbqt, gro
}

interface MoleculeViewerProps {
  /** Raw file URL (same-origin) to load the structure from. */
  src: string;
  ext: string;
}

/**
 * Interactive 3D molecule viewer powered by Mol* (molstar) — the same engine
 * RCSB/PDBe use. Renders proteins, small molecules and complexes from
 * PDB/SDF/MOL2/MOL/XYZ/CIF/mmCIF with the built-in viewport toolbar.
 *
 * Mol* is heavy and touches the DOM, so it's loaded via dynamic import inside
 * the effect (keeps it off the initial bundle / critical path).
 */
export function MoleculeViewer({ src, ext }: MoleculeViewerProps) {
  const tm = useTMText();
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [status, setStatus] = React.useState<"loading" | "ready" | "error">(
    "loading",
  );

  React.useEffect(() => {
    let viewer: { dispose?: () => void } | null = null;
    let cancelled = false;

    (async () => {
      try {
        setStatus("loading");
        const { Viewer } = await import("molstar/lib/apps/viewer/app");
        if (cancelled || !containerRef.current) return;

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const v: any = await Viewer.create(containerRef.current, {
          layoutIsExpanded: false,
          layoutShowControls: false,
          layoutShowSequence: false,
          layoutShowLog: false,
          layoutShowLeftPanel: false,
          viewportShowExpand: true,
          viewportShowControls: true,
          collapseLeftPanel: true,
        });
        if (cancelled) {
          v.dispose?.();
          return;
        }
        viewer = v;

        await v.loadStructureFromUrl(src, molFormat(ext), false);
        if (!cancelled) setStatus("ready");
      } catch {
        if (!cancelled) setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
      try {
        viewer?.dispose?.();
      } catch {
        // ignore teardown errors
      }
    };
  }, [src, ext]);

  return (
    <div className="relative h-full w-full bg-white">
      <div ref={containerRef} className="absolute inset-0" />
      {status === "loading" && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center gap-2 text-sm text-tm-slate-soft">
          <LoaderCircle className="h-4 w-4 animate-spin text-tm-teal" />
          {tm("viewer.rendering3d")}
        </div>
      )}
      {status === "error" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-sm text-tm-slate-soft">
          <AlertCircle className="h-5 w-5 text-danger" />
          {tm("viewer.error3d")}
        </div>
      )}
    </div>
  );
}
