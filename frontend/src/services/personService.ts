import type { RegisteredPerson } from '../types';
import { apiClient } from './api';

export function mapBackendPerson(doc: any): RegisteredPerson {
  return {
    personId: doc.personReference || doc.personId || doc.id || (doc._id ? String(doc._id) : 'REG-0000'),
    fullName: doc.fullName || 'Registered Citizen',
    maskedMobile: doc.maskedMobile || (doc.mobile ? `${doc.mobile.substring(0, 6)}***` : '—'),
    email: doc.email || '—',
    city: doc.city || 'Bengaluru',
    identityStatus: (doc.identityStatus as any) || 'VERIFIED',
    linkedVehicles: Array.isArray(doc.linkedVehicles) ? doc.linkedVehicles.map((v: any) => ({
      plateNumber: v.plateNumber || '—',
      vehicleType: v.vehicleType || 'Two-Wheeler',
      model: v.vehicleModel || v.model || 'Motorcycle',
      registeredDate: v.registeredDate || '2025-01-01',
      status: v.registrationStatus || v.status || 'ACTIVE'
    })) : [],
    notificationHistory: Array.isArray(doc.notificationHistory) ? doc.notificationHistory : [],
    linkedCasesCount: doc.linkedCasesCount ?? 0
  };
}

class PersonService {
  async getRegisteredPersons(query?: string): Promise<{ persons: RegisteredPerson[]; isDemo: boolean; error?: string }> {
    const queryParam = query && query.trim() ? `?query=${encodeURIComponent(query.trim())}` : '';
    const res = await apiClient.get<any[]>(`/persons${queryParam}`);

    if (!res.success || !res.data) {
      return {
        persons: [],
        isDemo: false,
        error: res.error || 'Failed to retrieve persons registry from database.'
      };
    }

    const rawList = Array.isArray(res.data) ? res.data : [];
    const persons = rawList.map(mapBackendPerson);

    return {
      persons,
      isDemo: false
    };
  }

  async getPersonById(personId: string): Promise<RegisteredPerson | null> {
    const res = await apiClient.get<any>(`/persons/${encodeURIComponent(personId)}`);
    if (!res.success || !res.data) {
      return null;
    }
    return mapBackendPerson(res.data);
  }

  async reportMismatch(
    personId: string, 
    caseId: string, 
    reason: string, 
    userComments: string
  ): Promise<{ success: boolean; disputeId: string; message: string }> {
    const disputeId = `DISP-${Math.floor(10000 + Math.random() * 90000)}`;
    const res = await apiClient.post<any>('/persons/dispute', {
      disputeId,
      personId,
      caseId,
      reason,
      userComments
    });

    return {
      success: res.success,
      disputeId,
      message: res.message || 'Your review dispute has been logged. An enforcement review officer will examine the original camera footage.'
    };
  }
}

export const personService = new PersonService();
