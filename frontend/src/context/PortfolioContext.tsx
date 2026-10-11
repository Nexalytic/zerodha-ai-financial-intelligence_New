import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  ReactNode,
} from 'react';
import { PortfolioResponse } from '../types/portfolio';
import { fetchPortfolios } from '../api/portfolios';
import { parseApiError } from '../api/client';

export interface PortfolioContextType {
  portfolios: PortfolioResponse[];
  activePortfolioId: string | null;
  activePortfolio: PortfolioResponse | null;
  isLoading: boolean;
  error: string | null;
  setActivePortfolioId: (id: string | null) => void;
  refreshPortfolios: () => Promise<void>;
}

const PortfolioContext = createContext<PortfolioContextType | undefined>(undefined);

export interface PortfolioProviderProps {
  children: ReactNode;
  initialSelectedId?: string | null;
}

export const PortfolioProvider: React.FC<PortfolioProviderProps> = ({
  children,
  initialSelectedId = null,
}) => {
  const [portfolios, setPortfolios] = useState<PortfolioResponse[]>([]);
  const [activePortfolioId, setActivePortfolioIdState] = useState<string | null>(initialSelectedId);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadPortfolios = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchPortfolios();
      setPortfolios(data);

      setActivePortfolioIdState((currentId) => {
        if (data.length === 0) {
          return null;
        }
        // If current selected ID still exists in fresh data, keep it
        if (currentId && data.some((p) => p.id === currentId)) {
          return currentId;
        }
        // Default to first available portfolio
        return data[0].id;
      });
    } catch (err: unknown) {
      const parsed = parseApiError(err);
      setError(parsed.message || 'Failed to retrieve investment portfolios.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPortfolios();
  }, [loadPortfolios]);

  const setActivePortfolioId = useCallback((id: string | null) => {
    setActivePortfolioIdState(id);
  }, []);

  const refreshPortfolios = useCallback(async () => {
    await loadPortfolios();
  }, [loadPortfolios]);

  const activePortfolio = useMemo(() => {
    if (!activePortfolioId) return null;
    return portfolios.find((p) => p.id === activePortfolioId) || null;
  }, [portfolios, activePortfolioId]);

  const contextValue = useMemo<PortfolioContextType>(
    () => ({
      portfolios,
      activePortfolioId,
      activePortfolio,
      isLoading,
      error,
      setActivePortfolioId,
      refreshPortfolios,
    }),
    [
      portfolios,
      activePortfolioId,
      activePortfolio,
      isLoading,
      error,
      setActivePortfolioId,
      refreshPortfolios,
    ]
  );

  return (
    <PortfolioContext.Provider value={contextValue}>
      {children}
    </PortfolioContext.Provider>
  );
};

export function usePortfolio(): PortfolioContextType {
  const context = useContext(PortfolioContext);
  if (!context) {
    throw new Error('usePortfolio must be used within a PortfolioProvider');
  }
  return context;
}
