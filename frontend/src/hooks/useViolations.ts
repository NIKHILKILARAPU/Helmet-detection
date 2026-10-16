import { useState, useMemo } from 'react';
import { useApp } from '../context';
import type { ViolationStatus, ViolationType } from '../types';

export const useViolations = () => {
  const { cases, approveDraft, rejectCase, addNewCapturedCase } = useApp();
  const [statusFilter, setStatusFilter] = useState<ViolationStatus | 'ALL'>('ALL');
  const [typeFilter, setTypeFilter] = useState<ViolationType | 'ALL'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredCases = useMemo(() => {
    return cases.filter(c => {
      const matchesStatus = statusFilter === 'ALL' || c.status === statusFilter;
      const matchesType = typeFilter === 'ALL' || c.violationType === typeFilter;
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch = 
        q === '' ||
        c.id.toLowerCase().includes(q) ||
        c.camera.name.toLowerCase().includes(q) ||
        (c.linkedPerson?.fullName.toLowerCase().includes(q)) ||
        (c.linkedPerson?.vehiclePlate.toLowerCase().includes(q));
      return matchesStatus && matchesType && matchesSearch;
    });
  }, [cases, statusFilter, typeFilter, searchQuery]);

  return {
    cases,
    filteredCases,
    statusFilter,
    setStatusFilter,
    typeFilter,
    setTypeFilter,
    searchQuery,
    setSearchQuery,
    approveDraft,
    rejectCase,
    addNewCapturedCase
  };
};
