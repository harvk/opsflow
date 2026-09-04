import { useEffect, useState } from "react";

import { getServiceById } from "../services/serviceClient";

import type { AsyncState, ServiceDetails } from "../types/dashboard";

export function useServiceDetails(serviceId: string | undefined) {
  const [requestState, setRequestState] = useState<
    AsyncState<ServiceDetails | null>
  >({
    status: "loading",
    data: null,
    error: null,
  });

  useEffect(() => {
    let ignore = false;

    async function loadService() {
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
        const service = await getServiceById(serviceId);

        if (!ignore) {
          setRequestState({
            status: "success",
            data: service,
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
                : "Unable to load service.",
          });
        }
      }
    }

    void loadService();

    return () => {
      ignore = true;
    };
  }, [serviceId]);

  return requestState;
}
