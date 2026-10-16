import type { RegisteredPerson } from '../types';
import { INITIAL_REGISTERED_PERSONS } from '../data/mockData';
import { apiClient } from './api';

class PersonService {
  private localPersons: RegisteredPerson[] = [...INITIAL_REGISTERED_PERSONS];

  async getRegisteredPersons(query?: string): Promise<{ persons: RegisteredPerson[]; isDemo: boolean }> {
    const res = await apiClient.get<RegisteredPerson[]>('/persons', this.localPersons);
    let persons = res.isDemoData ? [...this.localPersons] : res.data;

    if (query && query.trim() !== '') {
      const q = query.toLowerCase().trim();
      persons = persons.filter(p => 
        p.fullName.toLowerCase().includes(q) ||
        p.personId.toLowerCase().includes(q) ||
        p.email.toLowerCase().includes(q) ||
        p.city.toLowerCase().includes(q) ||
        p.linkedVehicles.some(v => v.plateNumber.toLowerCase().includes(q))
      );
    }

    return {
      persons,
      isDemo: res.isDemoData
    };
  }

  async getPersonById(personId: string): Promise<RegisteredPerson | null> {
    const found = this.localPersons.find(p => p.personId === personId);
    return found || null;
  }

  async reportMismatch(
    personId: string, 
    caseId: string, 
    reason: string, 
    userComments: string
  ): Promise<{ success: boolean; disputeId: string; message: string }> {
    const disputeId = `DISP-${Math.floor(10000 + Math.random() * 90000)}`;
    await apiClient.post('/persons/dispute', {
      disputeId,
      personId,
      caseId,
      reason,
      userComments,
      submittedAt: new Date().toISOString()
    }, { received: true });

    return {
      success: true,
      disputeId,
      message: 'Your review dispute has been logged. An enforcement review officer will examine the original camera footage.'
    };
  }
}

export const personService = new PersonService();
