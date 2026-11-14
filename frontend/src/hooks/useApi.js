import { useCallback, useEffect, useRef, useState } from 'react'
import api, { apiErrorMessage } from '../services/api'

export function useApi(path, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(Boolean(path))
  const [error, setError] = useState(null)
  const [version, setVersion] = useState(0)
  const requestId = useRef(0)

  useEffect(() => {
    if (!path) {
      setData(null)
      setLoading(false)
      return undefined
    }
    const id = ++requestId.current
    setLoading(true)
    setError(null)
    api
      .get(path)
      .then((response) => {
        if (requestId.current === id) setData(response.data)
      })
      .catch((err) => {
        if (requestId.current === id) setError(apiErrorMessage(err))
      })
      .finally(() => {
        if (requestId.current === id) setLoading(false)
      })
    return () => {
      // Invalidate in-flight responses when the query changes.
      requestId.current += 1
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, version, ...deps])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  return { data, loading, error, reload, setData }
}

export function useDebounced(value, delay = 350) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}
