import { useEffect, useState } from "react";

import { getServices } from "../services/serviceClient";

import type { AsyncState, Service } from "../types/dashboard";

const initialState: AsyncState<Service[]> = {
  status: "loading",
  data: null,
  error: null,
};

export function useServices() {
  const [requestState, setRequestState] =
    useState<AsyncState<Service[]>>(initialState);

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let ignore = false;

    async function loadServices() {
      setRequestState({
        status: "loading",
        data: null,
        error: null,
      });

      try {
        const serviceData = await getServices();

        if (!ignore) {
          setRequestState({
            status: "success",
            data: serviceData,
            error: null,
          });
        }
      } catch (error) {
        if (!ignore) {
          setRequestState({
            status: "error",
            data: null,
            error: error instanceof Error ? error.message : "Unexpected error.",
          });
        }
      }
    }

    void loadServices();

    return () => {
      ignore = true;
    };
  }, [reloadKey]);

  function retry() {
    setReloadKey((value) => value + 1);
  }

  return {
    requestState,
    retry,
  };
}
