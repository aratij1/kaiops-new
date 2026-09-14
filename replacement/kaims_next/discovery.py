"""Bounded discovery of explicitly onboarded document roots; no global fallback."""
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path


class DocumentDiscovery:
    def __init__(self, roots, *, max_files=50, max_file_bytes=262144, max_total_bytes=2097152):
        self.roots = {name: Path(path).resolve() for name,path in roots.items()}
        self.max_files, self.max_file_bytes, self.max_total_bytes = max_files,max_file_bytes,max_total_bytes

    def collect(self, config):
        sources = config.get("document_sources", [])
        if not isinstance(sources,list):
            raise ValueError("document_sources must be a list")
        if len(sources)>20:
            raise ValueError("At most twenty document sources per application")
        outcomes=[]
        documents=[]
        total=0
        seen=set()
        for source in sources:
            source_id=source.get("id")
            if not source_id or source_id in seen:
                raise ValueError("Document sources require unique IDs")
            seen.add(source_id)
            outcome={"source_id":source_id,"required":source.get("required",True),"status":"no_matches","document_ids":[],"rejected":0}
            root=self.roots.get(source.get("root"))
            if root is None:
                outcome["status"]="not_configured"
                outcomes.append(outcome)
                continue
            target=(root/str(source.get("path","."))).resolve()
            if not target.is_relative_to(root):
                outcome["status"]="failed";outcome["reason"]="path_outside_configured_root"
                outcomes.append(outcome)
                continue
            if not target.exists():
                outcome["status"]="failed";outcome["reason"]="path_not_found"
                outcomes.append(outcome)
                continue
            candidates=[]
            if target.is_file(): candidates=[target]
            else:
                walk_errors=[]
                for number,(directory,dirs,files) in enumerate(os.walk(target,followlinks=False,onerror=walk_errors.append)):
                    if number>=500:
                        outcome["status"]="partial";outcome["reason"]="directory_scan_limit"
                        break
                    dirs[:]=sorted(d for d in dirs if d.lower() not in {".git","node_modules","landing","ingested_alerts"})
                    for name in sorted(files):
                        path=Path(directory)/name
                        if path.suffix.lower() in {".md",".txt",".json"}:
                            candidates.append(path)
                    if len(candidates)>self.max_files:
                        break
                if walk_errors:
                    outcome["status"]="partial";outcome["reason"]="directory_unreadable"
            for path in candidates:
                resolved=path.resolve()
                if len(documents)>=self.max_files or total>=self.max_total_bytes:
                    outcome["status"]="partial";outcome["reason"]="collection_limit"
                    break
                if not resolved.is_relative_to(root) or {"landing","ingested_alerts"}.intersection(part.lower() for part in resolved.parts):
                    outcome["rejected"]+=1
                    continue
                if resolved.suffix.lower() not in {".md",".txt",".json"}:
                    outcome["rejected"]+=1
                    continue
                try:
                    with resolved.open("rb") as stream: raw=stream.read(self.max_file_bytes+1)
                    if len(raw)>self.max_file_bytes or total+len(raw)>self.max_total_bytes:
                        outcome["rejected"]+=1
                        outcome["reason"]="document_size_limit"
                        continue
                    text=raw.decode("utf-8")
                    if not text.strip(): continue
                    digest=hashlib.sha256(raw).hexdigest()
                    document_id=hashlib.sha256((source_id+":"+str(resolved.relative_to(root))+":"+digest).encode()).hexdigest()
                    documents.append({"document_id":document_id,"source_id":source_id,"content_sha256":digest,
                        "source_uri":"document://"+source["root"]+"/"+resolved.relative_to(root).as_posix(),
                        "content":text,"kind":"reference_document","observed_at":None,
                        "collected_at":datetime.now(timezone.utc).isoformat()})
                    outcome["document_ids"].append(document_id)
                    total+=len(raw)
                except (OSError,UnicodeError):
                    outcome["rejected"]+=1
                    outcome["reason"]="document_unreadable"
            if outcome["status"]!="partial":
                outcome["status"]="partial" if outcome["rejected"] else "collected" if outcome["document_ids"] else "no_matches"
            outcomes.append(outcome)
        return {"sources":outcomes,"documents":documents,"bytes_collected":total}


def prepare_context(manifest, manifest_ref):
    sources=manifest.get("sources",[])
    required_ok=bool(sources) and all(s["status"]=="collected" for s in sources if s["required"])
    documents=manifest.get("documents",[])
    ready=required_ok and bool(documents)
    return {"baseline_ready":ready,"manifest_ref":manifest_ref,
            "document_refs":[d["document_id"] for d in documents],
            "source_outcomes":[{k:v for k,v in s.items() if k!="document_ids"} for s in sources],
            "incident_evidence_required":True,"reason":None if ready else "document_baseline_incomplete"}
