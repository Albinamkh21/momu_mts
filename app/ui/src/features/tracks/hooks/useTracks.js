import { useState, useEffect, useCallback } from 'react';
import { getTracks, getLabels } from '../api/tracks.api';

const hasActiveFilters = (filters) => {
  return Object.values(filters).some(value => value !== '');
};

export const useTracks = () => {
  const [loading, setLoading] = useState(false);
  const [labels, setLabels] = useState([]);

  useEffect(() => {
    getLabels().then(setLabels).catch(console.error);
  }, []);

  const fetchTracksData = useCallback(async (filters, limit, offset, sortModel) => {
    // Если нет активных фильтров, не загружаем данные
    if (!hasActiveFilters(filters)) {
      return { items: [], total: 0 };
    }

    setLoading(true);
    try {
      const params = { limit, offset };
      Object.keys(filters).forEach(key => {
        if (filters[key] !== '') params[key] = filters[key];
      });
      if (sortModel && sortModel.length > 0) {
        params.sort_by = sortModel[0].colId;
        params.sort_dir = sortModel[0].sort;
      }

      const response = await getTracks(params); 
      
      const totalHeader = response.headers['x-total-count'];
      const total = totalHeader ? parseInt(totalHeader, 10) : 0;

      return {
        items: response.data,
        total: total
      };
    } catch (err) {
      console.error("Ошибка загрузки треков:", err);
      return { items: [], total: 0 };
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, labels, fetchTracksData };
};