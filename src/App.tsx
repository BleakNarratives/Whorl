/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence, useScroll, useSpring } from 'motion/react';
import { 
  Shield, 
  Search, 
  Menu, 
  X, 
  Eye, 
  Lock,
  Compass,
  Sparkles,
  Activity,
  Zap,
  Terminal
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { globalField, type FieldEvent } from './lib/field';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// --- Types ---
interface ArchiveEntry {
  id: string;
  title: string;
  date: string;
  category: 'Secret' | 'Record' | 'Observation';
  content: string;
  author: string;
  locked?: boolean;
}

// --- Constants ---
const ARCHIVE_DATA: ArchiveEntry[] = [
  {
    id: '1',
    title: 'The Whispering Pines Incident',
    date: 'Autumn, 1892',
    category: 'Record',
    author: 'Headmaster Thorne',
    content: 'The trees began to speak in a tongue not heard since the founding. Students reported rhythmic tapping on dormitory windows, though no branches were near.'
  },
  {
    id: '2',
    title: 'Whorl Pattern Analysis',
    date: 'Winter, 1904',
    category: 'Observation',
    author: 'Professor Vane',
    content: 'The spirals found in the frost on the Great Hall windows match exactly the geometry of the library floor plan. Coincidence is unlikely.'
  },
  {
    id: '3',
    title: 'The Hidden Chamber beneath North Wing',
    date: 'Unknown',
    category: 'Secret',
    author: 'Anonymous',
    content: 'There is a door that only appears when the moon is in its third quarter. It smells of old paper and ozone.',
    locked: true
  },
  {
    id: '4',
    title: 'The Foxwood Crest Origin',
    date: 'Spring, 1845',
    category: 'Record',
    author: 'Lady Foxwood',
    content: 'The fox does not represent cunning, but the guardian of the threshold. The wood is not a place, but a state of mind.'
  }
];

// --- Components ---

const WhorlConsole = () => {
  const [lines, setLines] = useState<string[]>([]);
  const consoleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      const commands = [
        'SPAWN AGENT.ALPHA AT {0, 0, 0}',
        'OBSERVE FIELD.RESONANCE',
        'LEARN PATTERN.WHORL',
        'EMIT WAVE.EXCITATION',
        'RECALIBRATE HELICAL.AXIS',
        'SYNC MEATSUIT.INTERFACE',
        'DETECT ANOMALY.THRESHOLD'
      ];
      const cmd = commands[Math.floor(Math.random() * commands.length)];
      setLines(prev => [...prev.slice(-15), `> ${cmd} ... [OK]`]);
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [lines]);

  return (
    <div className="glass p-4 rounded-sm font-mono text-[10px] h-40 overflow-hidden flex flex-col">
      <div className="flex items-center gap-2 mb-2 opacity-50">
        <Terminal className="w-3 h-3" />
        <span className="uppercase tracking-widest">Whorl Interpreter v1.0.4</span>
      </div>
      <div ref={consoleRef} className="flex-1 overflow-y-auto space-y-1 opacity-70 scrollbar-hide">
        {lines.map((line, i) => (
          <div key={i} className={cn(line.includes('ANOMALY') ? 'text-red-400' : 'text-foxwood-gold')}>
            {line}
          </div>
        ))}
      </div>
    </div>
  );
};

const FieldMonitor = () => {
  const [events, setEvents] = useState<FieldEvent[]>([]);
  const [metrics, setMetrics] = useState(globalField.metrics);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unsubscribe = globalField.subscribe((event) => {
      setEvents(globalField.getHistory());
      setMetrics({ ...globalField.metrics });
    });

    // Register some demo agents
    globalField.registerAgent({
      id: 'stability_monitor',
      location: 'ui.threshold',
      respondsTo: ['ui.tilt', 'ui.shatter'],
      handler: (event) => {
        if (event.type === 'ui.shatter') {
          return "CRITICAL: Stability collapsed. Initiating containment.";
        }
        return null;
      },
      proximityThreshold: 1.0
    });

    globalField.registerAgent({
      id: 'wave_excitation_agent',
      location: 'ui.threshold',
      respondsTo: ['ui.tilt'],
      handler: (event, field) => {
        if (event.intensity > 0.8) {
          field.emit('wave.excitation', 'ui.threshold', { cause: 'high_tilt' }, 0.9, 'wave_excitation_agent');
          return "WAVE EXCITATION DETECTED: Field resonance peaking.";
        }
        return null;
      },
      proximityThreshold: 0.5
    });

    globalField.registerAgent({
      id: 'archive_guardian',
      location: 'archive',
      respondsTo: ['archive.access'],
      handler: (event) => {
        return `Access logged for entry ${event.payload.entryId}`;
      },
      proximityThreshold: 0.5
    });

    return unsubscribe;
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="fixed bottom-6 left-6 z-[100] w-80 pointer-events-auto">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-sm border border-foxwood-gold/20 overflow-hidden"
      >
        <div className="bg-foxwood-gold/10 px-4 py-2 flex justify-between items-center border-b border-foxwood-gold/20">
          <div className="flex items-center gap-2">
            <Activity className="w-3 h-3 text-foxwood-gold animate-pulse" />
            <span className="text-[10px] uppercase tracking-widest font-bold">Source Field Monitor</span>
          </div>
          <div className="flex gap-2">
            <div className="flex items-center gap-1">
              <Zap className="w-2 h-2 text-foxwood-gold" />
              <span className="text-[8px] font-mono opacity-60">{metrics.agentsActivated}</span>
            </div>
          </div>
        </div>
        
        <div 
          ref={scrollRef}
          className="h-48 overflow-y-auto p-4 font-mono text-[9px] space-y-2 bg-black/40 scrollbar-hide"
        >
          {events.length === 0 && (
            <p className="opacity-30 italic">Waiting for field excitations...</p>
          )}
          {events.map((event, i) => (
            <div key={i} className="border-l border-foxwood-gold/30 pl-2 py-1">
              <div className="flex justify-between opacity-50 mb-1">
                <span>{event.type}</span>
                <span>{new Date(event.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
              </div>
              <p className="text-foxwood-gold/80 truncate">@{event.location} | I:{event.intensity.toFixed(2)}</p>
            </div>
          ))}
        </div>

        <div className="px-4 py-2 bg-black/20 border-t border-foxwood-gold/10 flex justify-between text-[8px] font-mono opacity-50">
          <span>LATENCY: {(metrics.avgResponseTime).toFixed(2)}ms</span>
          <span>EMISSIONS: {metrics.eventsEmitted}</span>
        </div>
      </motion.div>
    </div>
  );
};

const WhorlBackground = () => (
  <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
    <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] whorl-gradient rounded-full blur-[100px]" />
    <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] whorl-gradient rounded-full blur-[120px]" />
    <svg className="absolute inset-0 w-full h-full opacity-[0.03]" xmlns="http://www.w3.org/2000/svg">
      <filter id="noise">
        <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch" />
      </filter>
      <rect width="100%" height="100%" filter="url(#noise)" />
    </svg>
    <div className="absolute inset-0 flex items-center justify-center opacity-[0.05]">
      <motion.div 
        animate={{ rotate: 360 }}
        transition={{ duration: 120, repeat: Infinity, ease: "linear" }}
        className="w-[150vh] h-[150vh] border-[1px] border-foxwood-gold rounded-full border-dashed"
      />
      <motion.div 
        animate={{ rotate: -360 }}
        transition={{ duration: 180, repeat: Infinity, ease: "linear" }}
        className="absolute w-[100vh] h-[100vh] border-[1px] border-foxwood-gold rounded-full border-dashed opacity-50"
      />
    </div>
  </div>
);

const Navbar = ({ onMenuToggle }: { onMenuToggle: () => void }) => (
  <nav className="fixed top-0 left-0 right-0 z-50 px-6 py-8 flex justify-between items-center bg-gradient-to-b from-foxwood-green to-transparent">
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 border border-foxwood-gold rounded-full flex items-center justify-center">
        <Shield className="w-5 h-5 text-foxwood-gold" />
      </div>
      <div>
        <h1 className="serif text-2xl tracking-widest uppercase font-light">Whorl</h1>
        <p className="text-[10px] uppercase tracking-[0.3em] opacity-60 font-medium">Foxwood Academy</p>
      </div>
    </div>
    
    <div className="hidden md:flex items-center gap-12">
      {['Archive', 'Faculty', 'Library', 'Threshold'].map((item) => (
        <a key={item} href="#" className="text-xs uppercase tracking-widest hover:text-foxwood-gold transition-colors">
          {item}
        </a>
      ))}
    </div>

    <button onClick={onMenuToggle} className="p-2 hover:bg-white/5 rounded-full transition-colors">
      <Menu className="w-6 h-6" />
    </button>
  </nav>
);

const EntryCard = ({ entry, onClick }: { entry: ArchiveEntry, onClick: () => void }) => (
  <motion.div 
    layout
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    whileHover={{ scale: 1.02 }}
    onClick={onClick}
    className="glass p-6 rounded-sm cursor-pointer group relative overflow-hidden"
  >
    <div className="absolute top-0 left-0 w-1 h-full bg-foxwood-gold/30 group-hover:bg-foxwood-gold transition-colors" />
    
    <div className="flex justify-between items-start mb-4">
      <span className="text-[10px] uppercase tracking-widest opacity-50 font-bold">{entry.category}</span>
      <span className="text-[10px] uppercase tracking-widest opacity-50">{entry.date}</span>
    </div>
    
    <h3 className="serif text-xl mb-2 group-hover:text-foxwood-gold transition-colors">{entry.title}</h3>
    <p className="text-xs opacity-60 mb-4 italic">By {entry.author}</p>
    
    <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-foxwood-gold font-bold">
      {entry.locked ? (
        <>
          <Lock className="w-3 h-3" />
          <span>Restricted Access</span>
        </>
      ) : (
        <>
          <Eye className="w-3 h-3" />
          <span>View Record</span>
        </>
      )}
    </div>
  </motion.div>
);

const DetailView = ({ entry, onClose }: { entry: ArchiveEntry, onClose: () => void }) => {
  useEffect(() => {
    globalField.emit('archive.access', 'archive', { entryId: entry.id, title: entry.title }, entry.locked ? 0.9 : 0.3);
  }, [entry]);

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-foxwood-green/90 backdrop-blur-md"
    >
      <motion.div 
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        className="max-w-2xl w-full glass p-12 rounded-sm relative"
      >
        <button onClick={onClose} className="absolute top-6 right-6 p-2 hover:bg-white/5 rounded-full transition-colors">
          <X className="w-6 h-6" />
        </button>
        
        <div className="mb-8">
          <span className="text-xs uppercase tracking-[0.3em] text-foxwood-gold font-bold block mb-2">{entry.category}</span>
          <h2 className="serif text-4xl mb-2">{entry.title}</h2>
          <div className="flex justify-between items-center border-b border-foxwood-gold/20 pb-4">
            <p className="text-sm italic opacity-70">Recorded by {entry.author}</p>
            <p className="text-xs opacity-50">{entry.date}</p>
          </div>
        </div>
        
        <div className="serif text-lg leading-relaxed opacity-90 space-y-4">
          {entry.locked ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Lock className="w-12 h-12 text-foxwood-gold mb-4 opacity-50" />
              <p className="italic">This record is sealed by the High Council.</p>
              <p className="text-sm opacity-50 mt-2">Requires Level 4 Clearance or Headmaster's Sigil.</p>
            </div>
          ) : (
            <p>{entry.content}</p>
          )}
        </div>
        
        <div className="mt-12 pt-6 border-t border-foxwood-gold/10 flex justify-between items-center">
          <div className="flex gap-4">
            <button className="text-[10px] uppercase tracking-widest hover:text-foxwood-gold transition-colors">Print Facsimile</button>
            <button className="text-[10px] uppercase tracking-widest hover:text-foxwood-gold transition-colors">Cross Reference</button>
          </div>
          <div className="w-8 h-8 border border-foxwood-gold/30 rounded-full flex items-center justify-center opacity-30">
            <Shield className="w-4 h-4" />
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

// --- Components ---

const ThresholdSection = () => {
  const [seed, setSeed] = useState(Math.random());
  const [intensity, setIntensity] = useState(0.5);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [isMeatsuitMode, setIsMeatsuitMode] = useState(false);
  const [shatter, setShatter] = useState(false);
  const [stability, setStability] = useState(100);
  const [target, setTarget] = useState({ x: (Math.random() - 0.5) * 1.5, y: (Math.random() - 0.5) * 1.5 });
  const [resonance, setResonance] = useState(0);
  const [excitations, setExcitations] = useState<number[]>([]);

  useEffect(() => {
    const unsubscribe = globalField.subscribe((event) => {
      if (event.type === 'wave.excitation') {
        setExcitations(prev => [...prev.slice(-5), Math.random()]);
      }
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (!isMeatsuitMode) return;

    const handleOrientation = (event: DeviceOrientationEvent) => {
      const { beta, gamma } = event;
      // Add some "jitter" to make it harder
      const jitterX = (Math.random() - 0.5) * 0.05;
      const jitterY = (Math.random() - 0.5) * 0.05;
      
      const x = ((gamma || 0) / 45) + jitterX; 
      const y = ((beta || 0) / 45) + jitterY;  
      setTilt({ x, y });

      // Calculate distance to target
      const dx = x - target.x;
      const dy = y - target.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      
      // Resonance increases when close to target
      const newResonance = Math.max(0, 1 - dist);
      setResonance(prev => prev * 0.9 + newResonance * 0.1);

      // Stability decays faster if far from target or tilting too much
      const totalTilt = Math.abs(x) + Math.abs(y);
      const decayBase = totalTilt * 50;
      const targetPenalty = dist * 30;
      const newStability = Math.max(0, stability - (decayBase + targetPenalty) * 0.01);
      
      setStability(newStability);

      globalField.emit('ui.tilt', 'ui.threshold', { x, y, stability: newStability, resonance: newResonance }, totalTilt / 2);

      if (newStability <= 0 && !shatter) {
        setShatter(true);
        globalField.emit('ui.shatter', 'ui.threshold', { x, y }, 1.0);
      }
    };

    const interval = setInterval(() => {
      // Slowly move the target to keep the user on their toes
      setTarget(prev => ({
        x: Math.max(-1.5, Math.min(1.5, prev.x + (Math.random() - 0.5) * 0.2)),
        y: Math.max(-1.5, Math.min(1.5, prev.y + (Math.random() - 0.5) * 0.2))
      }));
    }, 2000);

    if (typeof (DeviceOrientationEvent as any).requestPermission === 'function') {
      (DeviceOrientationEvent as any).requestPermission()
        .then((permissionState: string) => {
          if (permissionState === 'granted') {
            window.addEventListener('deviceorientation', handleOrientation);
          }
        })
        .catch(console.error);
    } else {
      window.addEventListener('deviceorientation', handleOrientation);
    }

    return () => {
      window.removeEventListener('deviceorientation', handleOrientation);
      clearInterval(interval);
    };
  }, [isMeatsuitMode, shatter, stability, target]);

  const generateWhorl = () => {
    setSeed(Math.random());
    setShatter(false);
    setStability(100);
    setResonance(0);
    setTarget({ x: (Math.random() - 0.5) * 1.5, y: (Math.random() - 0.5) * 1.5 });
    globalField.emit('ui.recalibrate', 'ui.threshold', { seed: Math.random() }, 0.5);
  };

  const currentIntensity = isMeatsuitMode 
    ? Math.max(0, Math.min(1, intensity + (100 - stability) / 100 + resonance * 0.5))
    : intensity;

  return (
    <section className="mt-24 pt-24 border-t border-foxwood-gold/10">
      <div className="flex flex-col lg:flex-row gap-12 items-start">
        <div className="flex-1 space-y-8">
          <div>
            <p className="text-xs uppercase tracking-[0.5em] text-foxwood-gold font-bold mb-4">The Threshold</p>
            <h2 className="serif text-4xl mb-6">Attune your <span className="italic gold-text">Essence</span>.</h2>
            <p className="opacity-70 leading-relaxed">
              The Meatsuit Interface allows direct neural coupling with the Whorl. 
              Maintain stability by counteracting the field's natural drift. 
              <span className="block mt-2 text-foxwood-gold/80 italic">Seek the resonance target to stabilize the excitation waves.</span>
            </p>
          </div>
          
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-4">
              <button 
                onClick={() => setIsMeatsuitMode(!isMeatsuitMode)}
                className={cn(
                  "px-4 py-2 glass text-[10px] uppercase tracking-widest transition-all",
                  isMeatsuitMode ? "border-foxwood-gold text-foxwood-gold" : "opacity-50"
                )}
              >
                {isMeatsuitMode ? "Meatsuit Interface: Active" : "Meatsuit Interface: Offline"}
              </button>
              {isMeatsuitMode && (
                <div className="flex items-center gap-3">
                  <span className={cn(
                    "text-[10px] uppercase tracking-widest animate-pulse",
                    stability < 30 ? "text-red-500" : "text-foxwood-gold"
                  )}>
                    {stability < 30 ? "Critical Instability" : "Resonance Synced"}
                  </span>
                  <div className="flex gap-1">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <div 
                        key={i}
                        className={cn(
                          "w-1 h-3 rounded-full transition-all duration-300",
                          resonance > (i / 5) ? "bg-foxwood-gold shadow-[0_0_8px_rgba(197,160,89,0.5)]" : "bg-white/10"
                        )}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {isMeatsuitMode && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="glass p-4 rounded-sm">
                    <p className="text-[10px] uppercase tracking-widest opacity-50 mb-1">Stability</p>
                    <p className={cn("font-mono text-xs", stability < 30 ? "text-red-500" : "gold-text")}>{stability.toFixed(1)}%</p>
                  </div>
                  <div className="glass p-4 rounded-sm">
                    <p className="text-[10px] uppercase tracking-widest opacity-50 mb-1">Resonance</p>
                    <p className="font-mono text-xs gold-text">{(resonance * 100).toFixed(1)}%</p>
                  </div>
                  <div className="glass p-4 rounded-sm">
                    <p className="text-[10px] uppercase tracking-widest opacity-50 mb-1">Lateral</p>
                    <p className="font-mono text-xs gold-text">{(tilt.x * 100).toFixed(1)}%</p>
                  </div>
                  <div className="glass p-4 rounded-sm">
                    <p className="text-[10px] uppercase tracking-widest opacity-50 mb-1">Axial</p>
                    <p className="font-mono text-xs gold-text">{(tilt.y * 100).toFixed(1)}%</p>
                  </div>
                </div>
                <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
                  <motion.div 
                    animate={{ width: `${stability}%`, backgroundColor: stability < 30 ? '#ef4444' : '#c5a059' }}
                    className="h-full"
                  />
                </div>
              </div>
            )}

            {!isMeatsuitMode && (
              <div>
                <label className="text-[10px] uppercase tracking-widest opacity-50 block mb-2">Resonance Intensity</label>
                <input 
                  type="range" 
                  min="0" 
                  max="1" 
                  step="0.01" 
                  value={intensity}
                  onChange={(e) => setIntensity(parseFloat(e.target.value))}
                  className="w-full accent-foxwood-gold"
                />
              </div>
            )}

            <div className="flex gap-4">
              <button 
                onClick={generateWhorl}
                className="flex-1 px-8 py-3 glass border-foxwood-gold/30 hover:border-foxwood-gold text-xs uppercase tracking-widest transition-all"
              >
                {shatter ? "Reconstruct Sigil" : "Recalibrate Sigil"}
              </button>
            </div>
          </div>

          <WhorlConsole />
        </div>
        
        <div className="w-full md:w-[500px] aspect-square glass rounded-full flex items-center justify-center p-8 relative group overflow-hidden">
          {/* Target Indicator */}
          {isMeatsuitMode && !shatter && (
            <motion.div 
              animate={{ 
                x: target.x * 100, 
                y: target.y * 100,
                scale: [1, 1.2, 1],
                opacity: [0.2, 0.4, 0.2]
              }}
              transition={{ scale: { repeat: Infinity, duration: 2 } }}
              className="absolute w-12 h-12 border border-foxwood-gold/40 rounded-full flex items-center justify-center pointer-events-none"
            >
              <div className="w-1 h-1 bg-foxwood-gold rounded-full" />
            </motion.div>
          )}

          <div className={cn(
            "absolute inset-0 rounded-full border border-foxwood-gold/10 group-hover:border-foxwood-gold/30 transition-colors",
            shatter && "border-red-500/50"
          )} />
          
          <motion.div 
            animate={shatter ? {
              x: [0, -4, 4, -4, 4, 0],
              y: [0, 4, -4, 4, -4, 0],
            } : {
              x: tilt.x * 20,
              y: tilt.y * 20,
              rotate: tilt.x * 15,
            }}
            transition={shatter ? { repeat: Infinity, duration: 0.05 } : { type: 'spring', damping: 20, stiffness: 120 }}
            className="w-full h-full"
          >
            <svg viewBox="0 0 100 100" className="w-full h-full overflow-visible">
              {/* Excitation Waves */}
              {excitations.map((ex, idx) => (
                <motion.circle
                  key={`ex-${idx}`}
                  initial={{ r: 0, opacity: 0.5 }}
                  animate={{ r: 100, opacity: 0 }}
                  transition={{ duration: 3, ease: "easeOut" }}
                  cx="50"
                  cy="50"
                  fill="none"
                  stroke="#c5a059"
                  strokeWidth="0.2"
                />
              ))}

              <motion.path
                key={seed}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ 
                  pathLength: shatter ? 0.1 : 1, 
                  opacity: shatter ? [0.2, 0.8, 0.2] : 1,
                  scale: shatter ? 1.5 : 1,
                }}
                transition={{ duration: 2, ease: "easeInOut" }}
                d={`M 50 50 ${Array.from({ length: 30 }).map((_, i) => {
                  const angle = (i * 0.4 + seed + (isMeatsuitMode ? tilt.x * 0.3 : 0)) * Math.PI * 2;
                  const radius = i * (1.5 + currentIntensity * 4);
                  // Add wave distortion
                  const waveDist = Math.sin(i * 0.5 + Date.now() * 0.005) * (resonance * 5);
                  return `L ${50 + Math.cos(angle) * (radius + waveDist)} ${50 + Math.sin(angle) * (radius + waveDist)}`;
                }).join(' ')}`}
                fill="none"
                stroke="currentColor"
                strokeWidth={shatter ? "2" : "0.5"}
                className={cn(
                  "transition-colors duration-300",
                  shatter ? "text-red-500" : "text-foxwood-gold opacity-60"
                )}
              />
              
              {Array.from({ length: 12 }).map((_, i) => (
                <motion.circle
                  key={`${seed}-${i}`}
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ 
                    scale: shatter ? [1, 1.5, 1] : 1,
                    opacity: shatter ? 0.1 : 0.1 + (resonance * 0.2),
                    x: isMeatsuitMode ? tilt.x * (i + 1) * 4 : 0,
                    y: isMeatsuitMode ? tilt.y * (i + 1) * 4 : 0,
                  }}
                  transition={{ delay: i * 0.05, duration: 1 }}
                  cx="50"
                  cy="50"
                  r={4 + i * 5}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="0.1"
                  className={cn(
                    "transition-colors duration-300",
                    shatter ? "text-red-500" : "text-foxwood-gold"
                  )}
                />
              ))}
            </svg>
          </motion.div>

          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            {shatter ? (
              <div className="flex flex-col items-center">
                <X className="w-16 h-16 text-red-500 opacity-50 animate-ping" />
                <p className="text-[10px] uppercase tracking-[0.8em] text-red-500 mt-4 font-bold">System Fracture</p>
              </div>
            ) : (
              <div className="relative">
                <Sparkles className="w-8 h-8 text-foxwood-gold opacity-20 animate-pulse" />
                {resonance > 0.8 && (
                  <motion.div 
                    animate={{ scale: [1, 2], opacity: [0.5, 0] }}
                    transition={{ repeat: Infinity, duration: 1 }}
                    className="absolute inset-0 border border-foxwood-gold rounded-full"
                  />
                )}
              </div>
            )}
          </div>

          {isMeatsuitMode && !shatter && (
            <div className="absolute bottom-12 left-1/2 -translate-x-1/2 flex flex-col items-center">
              <p className="text-[8px] uppercase tracking-[0.3em] opacity-30 mb-2">Neural Link Integrity</p>
              <div className="flex gap-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div 
                    key={i}
                    className={cn(
                      "w-2 h-1 rounded-full transition-all duration-500",
                      stability > (i + 1) * 20 ? "bg-foxwood-gold" : "bg-white/5"
                    )}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};

export default function App() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001
  });

  const [selectedEntry, setSelectedEntry] = useState<ArchiveEntry | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const filteredEntries = ARCHIVE_DATA.filter(entry => 
    entry.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    entry.content.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen relative">
      <motion.div 
        className="fixed top-0 left-0 right-0 h-1 bg-foxwood-gold z-[60] origin-left"
        style={{ scaleX }}
      />
      <WhorlBackground />
      <FieldMonitor />
      
      <Navbar onMenuToggle={() => setIsMenuOpen(true)} />
      
      <main className="relative z-10 pt-32 pb-24 px-6 max-w-7xl mx-auto">
        <header className="mb-16">
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-4 mb-4"
          >
            <div className="h-[1px] w-12 bg-foxwood-gold" />
            <span className="text-xs uppercase tracking-[0.5em] text-foxwood-gold font-bold">The Digital Archive</span>
          </motion.div>
          
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-8">
            <motion.h2 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="serif text-5xl md:text-7xl max-w-2xl leading-tight"
            >
              Unveiling the <span className="italic gold-text">Patterns</span> of Foxwood.
            </motion.h2>
            
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
              className="relative w-full md:w-80"
            >
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 opacity-40" />
              <input 
                type="text" 
                placeholder="Search the records..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full glass bg-transparent border-none rounded-full py-3 pl-12 pr-6 text-sm focus:ring-1 focus:ring-foxwood-gold outline-none transition-all"
              />
            </motion.div>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredEntries.map((entry) => (
            <EntryCard 
              key={entry.id} 
              entry={entry} 
              onClick={() => setSelectedEntry(entry)} 
            />
          ))}
        </div>

        <ThresholdSection />

        {filteredEntries.length === 0 && (
          <div className="text-center py-24 opacity-40 italic serif text-xl">
            No records found in the current temporal stream.
          </div>
        )}
      </main>

      <footer className="relative z-10 border-t border-foxwood-gold/10 py-12 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="flex items-center gap-4">
            <Shield className="w-5 h-5 text-foxwood-gold opacity-50" />
            <p className="text-[10px] uppercase tracking-widest opacity-40">
              &copy; 1842 - 2026 Foxwood Academy. All Rights Reserved.
            </p>
          </div>
          
          <div className="flex gap-8">
            {['Privacy', 'Terms', 'The Threshold'].map(item => (
              <a key={item} href="#" className="text-[10px] uppercase tracking-widest opacity-40 hover:opacity-100 transition-opacity">
                {item}
              </a>
            ))}
          </div>
        </div>
      </footer>

      <AnimatePresence>
        {selectedEntry && (
          <DetailView 
            entry={selectedEntry} 
            onClose={() => setSelectedEntry(null)} 
          />
        )}
      </AnimatePresence>

      {/* Sidebar Menu */}
      <AnimatePresence>
        {isMenuOpen && (
          <motion.div 
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed inset-y-0 right-0 z-[110] w-full md:w-96 glass bg-foxwood-green/95 backdrop-blur-xl p-12 flex flex-col"
          >
            <button onClick={() => setIsMenuOpen(false)} className="self-end p-2 hover:bg-white/5 rounded-full transition-colors mb-12">
              <X className="w-8 h-8" />
            </button>
            
            <div className="space-y-8 flex-1">
              <div className="mb-12">
                <p className="text-xs uppercase tracking-[0.5em] text-foxwood-gold font-bold mb-4">Navigation</p>
                <div className="flex flex-col gap-6">
                  {['The Archive', 'Faculty Directory', 'Library Catalog', 'Student Records', 'The Threshold'].map((item, i) => (
                    <motion.a 
                      key={item}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.1 }}
                      href="#" 
                      className="serif text-3xl hover:text-foxwood-gold transition-colors"
                    >
                      {item}
                    </motion.a>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs uppercase tracking-[0.5em] text-foxwood-gold font-bold mb-4">Academy Status</p>
                <div className="space-y-4">
                  <div className="flex justify-between items-center text-xs">
                    <span className="opacity-50">Current Phase</span>
                    <span className="gold-text">Waxing Gibbous</span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="opacity-50">Archive Integrity</span>
                    <span className="gold-text">98.4%</span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="opacity-50">Active Guardians</span>
                    <span className="gold-text">12</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-auto pt-12 border-t border-foxwood-gold/10">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 border border-foxwood-gold/30 rounded-full flex items-center justify-center">
                  <Compass className="w-6 h-6 text-foxwood-gold" />
                </div>
                <div>
                  <p className="serif text-lg">Seek the Whorl.</p>
                  <p className="text-[10px] uppercase tracking-widest opacity-40">Foxwood Academy Portal</p>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
