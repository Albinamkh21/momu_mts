import { useState, useEffect, useCallback } from 'react';
import { getRightHolders, getLabels } from '../api/rightHolders.api';

export const useRightHolders = () => {
  const [loading, setLoading] = useState(false);
  const [labels, setLabels] = useState([]);

  useEffect(() => {
    getLabels().then(setLabels).catch(console.error);
  }, []);

  const fetchRightHoldersData = useCallback(async (filters, limit, offset, sortModel) => {
    setLoading(true);
    try {
      const params = { limit, offset };
      Object.keys(filters).forEach((key) => {
        if (filters[key] !== '') params[key] = filters[key];
      });
      if (sortModel && sortModel.length > 0) {
        params.sort_by = sortModel[0].colId;
        params.sort_dir = sortModel[0].sort;
      }

      const data = await getRightHolders(params);
      return { items: data.items, total: data.total };
    } catch (err) {
      console.error('Ошибка загрузки правообладателей:', err);
      return { items: [], total: 0 };
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, labels, fetchRightHoldersData };
};
