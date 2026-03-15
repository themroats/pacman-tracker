import { useEffect, useState } from "react";
import { citiesApi } from "@/api/client";
import { useAppStore } from "@/store";

const POLL_INTERVAL_MS = 5000;

export function useCityCatalog() {
  const cities = useAppStore((s) => s.cities);
  const setCities = useAppStore((s) => s.setCities);

  const [isBootstrapping, setIsBootstrapping] = useState(false);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const loadCities = async () => {
      try {
        const response = await citiesApi.list();
        if (cancelled) return;

        setCities(response.cities);
        setBootstrapError(response.bootstrap_error ?? null);

        const bootstrapping =
          response.bootstrap_status === "loading" ||
          (response.cities.length === 0 && response.bootstrap_status !== "failed");

        setIsBootstrapping(bootstrapping);

        if (bootstrapping) {
          timer = setTimeout(loadCities, POLL_INTERVAL_MS);
        }
      } catch (error) {
        if (cancelled) return;
        setIsBootstrapping(false);
        setBootstrapError(error instanceof Error ? error.message : "Failed to load cities");
      }
    };

    loadCities();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [setCities]);

  return {
    cities,
    isBootstrapping,
    bootstrapError,
  };
}