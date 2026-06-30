import { useEffect, useState } from 'react';
import { classifyApiError } from '../apiClient';

export function useApiResource(load, deps) {
  const [resource, setResource] = useState({ status: 'loading', data: null, error: null });
  const [reloadToken, setReloadToken] = useState(0);
  useEffect(() => {
    let active = true;
    setResource({ status: 'loading', data: null, error: null });
    load()
      .then((data) => active && setResource({ status: 'ready', data, error: null }))
      .catch((error) => {
        if (!active) return;
        const failure = classifyApiError(error);
        setResource({ status: failure.kind, data: null, error: failure.message });
      });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadToken]);
  return [resource, () => setReloadToken((v) => v + 1)];
}
