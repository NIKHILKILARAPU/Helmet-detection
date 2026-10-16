import { useContext } from 'react';
import { AppContext } from './appContextDefinition';
import type { AppContextType } from './appContextDefinition';

export const useApp = (): AppContextType => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
