import { useState, useCallback } from 'react';
import { getContractAnnexes } from '../api/contractAnnex.api';

export const useContractAnnexes = (contractId) => {
  const [loading, setLoading] = useState(false);

  const fetchContractAnnexesData = useCallback(async (filters, limit, offset, sortModel) => {
    if (!contractId) {
      return { items: [], total: 0 };
    }
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

      const data = await getContractAnnexes(contractId, params);
      return { items: data.items, total: data.total };
    } catch (err) {
      console.error('Ошибка загрузки приложений к договору:', err);
      return { items: [], total: 0 };
    } finally {
      setLoading(false);
    }
  }, [contractId]);

  return { loading, fetchContractAnnexesData };
};
