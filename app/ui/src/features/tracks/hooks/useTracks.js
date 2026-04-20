import { useState, useEffect, useCallback } from 'react';
import { getTracks, getLabels } from '../api/tracks.api';

export const useTracks = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [labels, setLabels] = useState([]);

  const fetchTracks = useCallback(async (filters = {}) => {
    setLoading(true);
    try {
      const params = { limit: 100 };
      if (filters.title) params.title = filters.title;
      if (filters.isrc) params.isrc = filters.isrc;
      if (filters.label_own_code) params.label_own_code = filters.label_own_code;
      if (filters.label_id) params.label_id = filters.label_id;
      const res = await getTracks(params);
      setData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTracks();
    getLabels().then(setLabels).catch(console.error);
  }, [fetchTracks]);

  return { data, loading, labels, refetch: fetchTracks };
};