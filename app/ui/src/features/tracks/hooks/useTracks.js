import { useState, useEffect, useCallback } from 'react';
import { getTracks, getLabels } from '../api/tracks.api';

export const useTracks = () => {
  const [loading, setLoading] = useState(false);
  const [labels, setLabels] = useState([]);

  useEffect(() => {
    getLabels().then(setLabels).catch(console.error);
  }, []);

  const fetchTracksData = useCallback(async (filters, limit, offset) => {
    setLoading(true);
    try {
      const params = { limit, offset };
      Object.keys(filters).forEach(key => {
        if (filters[key] !== '') params[key] = filters[key];
      });

      // Теперь здесь полный объект ответа Axios
      const response = await getTracks(params); 
      
      // Читаем заголовок (Axios приводит ключи к нижнему регистру автоматически)
      const totalHeader = response.headers['x-total-count'];
      const total = totalHeader ? parseInt(totalHeader, 10) : 0;

      return {
        items: response.data, // Сами треки теперь лежат в .data
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