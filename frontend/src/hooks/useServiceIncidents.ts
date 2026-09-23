import { useEffect, useState } from "react";

import { getServiceIncidents } from "../services/serviceClient";

import type { AsyncState } from "../types/dashboard";
import type { Incident } from "../types/incidents";

export function useServiceIncidents(serviceId: string | undefined) {
  const [requestState, setRequestState] = useState<AsyncState<Incident[]>>({
    status: "loading",
    data: null,
    error: null,
  });

  useEffect(() => {
    let ignore = false;

    async function loadIncidents() {
      if (!serviceId) {
        setRequestState({
          status: "error",
          data: null,
          error: "A service identifier was not provided.",
        });

        return;
      }

      setRequestState({
        status: "loading",
        data: null,
        error: null,
      });

      try {
        const incidents = await getServiceIncidents(serviceId);

        if (!ignore) {
          setRequestState({
            status: "success",
            data: incidents,
            error: null,
          });
        }
      } catch (error) {
        if (!ignore) {
          setRequestState({
            status: "error",
            data: null,
            error:
              error instanceof Error
                ? error.message
                : "Unable to load service incidents.",
          });
        }
      }
    }

    void loadIncidents();

    return () => {
      ignore = true;
    };
  }, [serviceId]);

  return requestState;
}
