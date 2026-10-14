import { useNavigate } from "react-router-dom";
import { durableIncidentPath, type IncidentIdentitySource } from "./incidentNavigation";

export function useOpenIncident() {
  const navigate = useNavigate();
  return (source: IncidentIdentitySource | null | undefined, stage?: string) => {
    const path = durableIncidentPath(source);
    if (!path) return;
    if (stage && stage !== "overview") {
      navigate(`${path}?stage=${encodeURIComponent(stage)}`);
    } else {
      navigate(path);
    }
  };
}
