/**
 * Field-Excited Programming (FEP) Runtime - TypeScript Implementation
 * Event bus + proximity-based agent coordination
 */

export type FieldEventType = string;
export type Location = string;

export interface FieldEvent {
  type: FieldEventType;
  location: Location;
  payload: Record<string, any>;
  intensity: number; // 0.0 to 1.0
  timestamp: number;
  sourceAgent?: string;
}

export interface Agent {
  id: string;
  location: Location;
  respondsTo: string[]; // Event patterns (e.g., "error.*")
  handler: (event: FieldEvent, field: Field, distance: number) => Promise<string | null> | string | null;
  proximityThreshold: number;
}

export class Field {
  private events: FieldEvent[] = [];
  private agents: Map<string, Agent> = new Map();
  public state: Record<string, any> = {};
  private maxHistory: number;

  public metrics = {
    eventsEmitted: 0,
    agentsActivated: 0,
    avgResponseTime: 0,
  };

  private listeners: ((event: FieldEvent) => void)[] = [];

  constructor(maxHistory: number = 100) {
    this.maxHistory = maxHistory;
  }

  public subscribe(listener: (event: FieldEvent) => void) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  public registerAgent(agent: Agent) {
    this.agents.set(agent.id, agent);
    console.log(`[FIELD] Agent registered: ${agent.id} at ${agent.location}`);
  }

  public async emit(type: string, location: string, payload: Record<string, any> = {}, intensity: number = 0.5, source?: string) {
    const event: FieldEvent = {
      type,
      location,
      payload,
      intensity,
      timestamp: Date.now(),
      sourceAgent: source,
    };

    this.events.push(event);
    if (this.events.length > this.maxHistory) {
      this.events.shift();
    }

    this.metrics.eventsEmitted++;
    this.listeners.forEach(l => l(event));

    console.log(`[FIELD] Event: ${type} at ${location} (intensity=${intensity.toFixed(2)})`);
    
    // Route to agents
    this.routeEvent(event);
    
    return event;
  }

  private async routeEvent(event: FieldEvent) {
    const startTime = Date.now();
    let activated = 0;

    for (const agent of this.agents.values()) {
      if (!this.matchesPattern(event.type, agent.respondsTo)) continue;

      const distance = this.calculateProximity(agent.location, event.location);
      if (distance > agent.proximityThreshold) continue;

      activated++;
      this.executeAgent(agent, event, distance);
    }

    if (activated > 0) {
      const elapsed = Date.now() - startTime;
      this.metrics.agentsActivated += activated;
      this.metrics.avgResponseTime = this.metrics.avgResponseTime * 0.9 + elapsed * 0.1;
    }
  }

  private async executeAgent(agent: Agent, event: FieldEvent, distance: number) {
    try {
      const result = await agent.handler(event, this, distance);
      if (result) {
        console.log(`[AGENT] ${agent.id} result: ${result}`);
      }
    } catch (error) {
      console.error(`[ERROR] Agent ${agent.id} failed:`, error);
      this.emit('agent.failure', agent.location, { agentId: agent.id, error: String(error) }, 0.7);
    }
  }

  private matchesPattern(type: string, patterns: string[]): boolean {
    return patterns.some(pattern => {
      if (pattern.endsWith('*')) {
        return type.startsWith(pattern.slice(0, -1));
      }
      return type === pattern;
    });
  }

  private calculateProximity(loc1: string, loc2: string): number {
    if (loc1 === loc2) return 0;
    const p1 = loc1.split('.');
    const p2 = loc2.split('.');
    let common = 0;
    for (let i = 0; i < Math.min(p1.length, p2.length); i++) {
      if (p1[i] === p2[i]) common++;
      else break;
    }
    const maxDepth = Math.max(p1.length, p2.length);
    return 1.0 - (common / maxDepth);
  }

  public getHistory() {
    return [...this.events];
  }
}

export const globalField = new Field();
