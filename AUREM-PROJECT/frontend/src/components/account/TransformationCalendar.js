import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Calendar, CheckCircle2, Circle, Clock, Sparkles, Download, Share2,
  Beaker, Zap, Sun, Shield, TrendingUp, Gift, ChevronDown, ChevronRight,
  Timer, Play, Pause, RotateCcw
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Phase configurations based on product categories
const PHASE_CONFIG = {
  resurfacing: {
    phase: 1,
    name: 'The Adjustment',
    days: '1-14',
    science: 'Mandelic Acid and HPR Retinoid begin "cellular reprogramming."',
    icon: Zap,
    color: 'purple',
    milestones: [
      { day: 1, title: 'First Application', description: 'Focus on the 60-second wait time. Feel the "Active Tingle."', critical: true },
      { day: 3, title: 'The Purge Begins', description: 'Dormant congestion is pushed out. Do not pick; use the Buffer (Step 2) to calm inflammation.' },
      { day: 7, title: 'Purge Peak', description: 'Maximum congestion clearing. Stay patient and consistent.' },
      { day: 14, title: 'Shedding Phase', description: 'Skin sheds dead cells faster. Slight flaking is the old skin giving way to the new.' }
    ]
  },
  brightening: {
    phase: 2,
    name: 'The Clarity Phase',
    days: '15-30',
    science: 'Tranexamic Acid and Alpha Arbutin begin suppressing deep melanin.',
    icon: Sun,
    color: 'amber',
    milestones: [
      { day: 21, title: 'Post-Purge Glow', description: 'Active breakouts should be 45% lower. The "glow" emerges.' },
      { day: 30, title: 'Pigment Lift', description: 'Melasma and sunspots look "shattered" or lighter at edges. Texture is 30% smoother.', critical: true }
    ]
  },
  repair: {
    phase: 3,
    name: 'The Structural Phase',
    days: '31-60',
    science: 'PDRN and Matrixyl 3000 begin reinforcing the dermal matrix (collagen).',
    icon: Shield,
    color: 'emerald',
    milestones: [
      { day: 45, title: 'Volume Shift', description: 'Fine lines around eyes and forehead appear "blurred."' },
      { day: 60, title: 'Barrier Resilience', description: 'Skin handles 55% active load with zero redness. Pores look minimized.', critical: true }
    ]
  },
  transformation: {
    phase: 4,
    name: 'The Transformation',
    days: '61-90',
    science: 'Full cellular turnover cycle is complete.',
    icon: Sparkles,
    color: 'pink',
    milestones: [
      { day: 75, title: 'Maximum Glow', description: 'DMI "Molecular Taxi" has delivered enough PDRN for visible skin thickening.' },
      { day: 90, title: 'Clinical Goal Reached', description: '60% faster results than individual use confirmed. Your skin exhibits the "AURA-GEN" glass finish.', critical: true, final: true }
    ]
  }
};

// All milestones in order for the full calendar
const ALL_MILESTONES = [
  ...PHASE_CONFIG.resurfacing.milestones.map(m => ({ ...m, phase: 'resurfacing' })),
  ...PHASE_CONFIG.brightening.milestones.map(m => ({ ...m, phase: 'brightening' })),
  ...PHASE_CONFIG.repair.milestones.map(m => ({ ...m, phase: 'repair' })),
  ...PHASE_CONFIG.transformation.milestones.map(m => ({ ...m, phase: 'transformation' }))
];

// Interactive 60-Second Countdown Timer Component
const CountdownTimer = ({ onComplete }) => {
  const [timeLeft, setTimeLeft] = useState(60);
  const [isRunning, setIsRunning] = useState(false);
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    let interval;
    if (isRunning && timeLeft > 0) {
      interval = setInterval(() => {
        setTimeLeft(prev => {
          if (prev <= 1) {
            setIsRunning(false);
            setIsComplete(true);
            onComplete?.();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isRunning, timeLeft, onComplete]);

  const handleStart = () => {
    setIsRunning(true);
    setIsComplete(false);
  };

  const handlePause = () => setIsRunning(false);
  
  const handleReset = () => {
    setTimeLeft(60);
    setIsRunning(false);
    setIsComplete(false);
  };

  const progress = ((60 - timeLeft) / 60) * 100;

  return (
    <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl p-4 border-2 border-amber-300">
      <div className="flex items-center gap-4">
        {/* Circular Progress Timer */}
        <div className="relative w-20 h-20 flex-shrink-0">
          <svg className="w-20 h-20 transform -rotate-90">
            <circle
              cx="40"
              cy="40"
              r="36"
              stroke="#FED7AA"
              strokeWidth="6"
              fill="none"
            />
            <circle
              cx="40"
              cy="40"
              r="36"
              stroke={isComplete ? "#22C55E" : "#F59E0B"}
              strokeWidth="6"
              fill="none"
              strokeDasharray={`${2 * Math.PI * 36}`}
              strokeDashoffset={`${2 * Math.PI * 36 * (1 - progress / 100)}`}
              strokeLinecap="round"
              className="transition-all duration-1000"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={`text-2xl font-bold ${isComplete ? 'text-green-600' : 'text-amber-700'}`}>
              {timeLeft}
            </span>
          </div>
        </div>

        <div className="flex-1">
          <h4 className="font-bold text-amber-800 mb-1">
            {isComplete ? '✓ Ready for Step 2!' : 'DMI Molecular Taxi Timer'}
          </h4>
          <p className="text-sm text-amber-700 mb-2">
            {isComplete 
              ? 'Apply Step 2 (Buffer) now while skin is still slightly damp.'
              : 'Wait 60 seconds for the actives to penetrate before Step 2.'
            }
          </p>
          
          {/* Control Buttons */}
          <div className="flex gap-2">
            {!isRunning && !isComplete && (
              <Button 
                size="sm" 
                onClick={handleStart}
                className="bg-amber-500 hover:bg-amber-600 text-white"
                data-testid="timer-start-btn"
              >
                <Play className="h-3 w-3 mr-1" />
                Start Timer
              </Button>
            )}
            {isRunning && (
              <Button 
                size="sm" 
                variant="outline"
                onClick={handlePause}
                className="border-amber-500 text-amber-700"
              >
                <Pause className="h-3 w-3 mr-1" />
                Pause
              </Button>
            )}
            {(isComplete || timeLeft < 60) && (
              <Button 
                size="sm" 
                variant="ghost"
                onClick={handleReset}
                className="text-amber-600"
              >
                <RotateCcw className="h-3 w-3 mr-1" />
                Reset
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Main Calendar Component
const TransformationCalendar = ({ orderId, comboName, customerName, orderDate }) => {
  const [completedMilestones, setCompletedMilestones] = useState([]);
  const [expandedPhases, setExpandedPhases] = useState(['resurfacing']);
  const [loading, setLoading] = useState(true);
  const [showShareModal, setShowShareModal] = useState(false);

  // Load progress from backend
  useEffect(() => {
    const loadProgress = async () => {
      try {
        const token = localStorage.getItem('reroots_token');
        if (!token || !orderId) {
          setLoading(false);
          return;
        }
        
        const res = await axios.get(`${API}/transformation-calendar/progress/${orderId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        
        setCompletedMilestones(res.data.completed_milestones || []);
      } catch (err) {
        console.log('Could not load progress:', err);
      } finally {
        setLoading(false);
      }
    };
    
    loadProgress();
  }, [orderId]);

  // Save progress to backend
  const toggleMilestone = async (day) => {
    const isCompleted = completedMilestones.includes(day);
    const newCompleted = isCompleted
      ? completedMilestones.filter(d => d !== day)
      : [...completedMilestones, day];
    
    setCompletedMilestones(newCompleted);
    
    // Check if Day 90 was just completed
    if (!isCompleted && day === 90) {
      setShowShareModal(true);
      // Trigger share results email
      try {
        const token = localStorage.getItem('reroots_token');
        await axios.post(`${API}/transformation-calendar/complete`, {
          order_id: orderId,
          customer_name: customerName
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
      } catch (err) {
        console.log('Could not send completion email:', err);
      }
    }
    
    // Save to backend
    try {
      const token = localStorage.getItem('reroots_token');
      if (token && orderId) {
        await axios.post(`${API}/transformation-calendar/progress`, {
          order_id: orderId,
          completed_milestones: newCompleted
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
    } catch (err) {
      console.log('Could not save progress:', err);
    }
  };

  const togglePhase = (phaseKey) => {
    setExpandedPhases(prev => 
      prev.includes(phaseKey) 
        ? prev.filter(p => p !== phaseKey)
        : [...prev, phaseKey]
    );
  };

  const totalMilestones = ALL_MILESTONES.length;
  const completedCount = completedMilestones.length;
  const progressPercent = Math.round((completedCount / totalMilestones) * 100);

  // Calculate current day based on order date
  const calculateCurrentDay = () => {
    if (!orderDate) return 1;
    const start = new Date(orderDate);
    const now = new Date();
    const diffTime = Math.abs(now - start);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return Math.min(diffDays, 90);
  };

  const currentDay = calculateCurrentDay();

  // Download PDF
  const handleDownloadPDF = () => {
    const pdfUrl = `${API}/transformation-calendar/pdf?order_id=${orderId}&customer_name=${encodeURIComponent(customerName || '')}&order_date=${encodeURIComponent(orderDate || '')}`;
    window.open(pdfUrl, '_blank');
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-purple-500 mx-auto" />
          <p className="text-gray-500 mt-2">Loading your transformation calendar...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <Card className="bg-gradient-to-r from-purple-600 via-pink-500 to-rose-400 text-white overflow-hidden">
        <CardContent className="p-6">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Calendar className="h-6 w-6" />
                <h2 className="text-2xl font-bold">12-Week Transformation Calendar</h2>
              </div>
              {customerName && (
                <p className="text-purple-100 mb-1">Personalized for: <strong>{customerName}</strong></p>
              )}
              {comboName && (
                <Badge className="bg-white/20 text-white mb-2">{comboName}</Badge>
              )}
              <p className="text-purple-100 text-sm">
                Day {currentDay} of 90 • {orderDate && `Started: ${new Date(orderDate).toLocaleDateString()}`}
              </p>
            </div>
            <Button 
              variant="secondary" 
              className="bg-white text-purple-700 hover:bg-purple-50"
              onClick={handleDownloadPDF}
              data-testid="download-calendar-pdf"
            >
              <Download className="h-4 w-4 mr-2" />
              Download PDF
            </Button>
          </div>
          
          {/* Progress Bar */}
          <div className="mt-4">
            <div className="flex justify-between text-sm mb-1">
              <span>{completedCount} of {totalMilestones} milestones</span>
              <span>{progressPercent}% Complete</span>
            </div>
            <div className="h-3 bg-white/20 rounded-full overflow-hidden">
              <div 
                className="h-full bg-white rounded-full transition-all duration-500"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 60-Second Timer Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Timer className="h-5 w-5 text-amber-500" />
            Interactive Protocol Timer
          </CardTitle>
        </CardHeader>
        <CardContent>
          <CountdownTimer onComplete={() => toast.success('Ready for Step 2! Apply now while skin is damp.')} />
        </CardContent>
      </Card>

      {/* Phase Cards */}
      {Object.entries(PHASE_CONFIG).map(([phaseKey, phase]) => {
        const PhaseIcon = phase.icon;
        const isExpanded = expandedPhases.includes(phaseKey);
        const phaseMilestones = ALL_MILESTONES.filter(m => m.phase === phaseKey);
        const phaseCompletedCount = phaseMilestones.filter(m => completedMilestones.includes(m.day)).length;
        const phaseComplete = phaseCompletedCount === phaseMilestones.length;
        
        const colorClasses = {
          purple: { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700', icon: 'text-purple-500' },
          amber: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', icon: 'text-amber-500' },
          emerald: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', icon: 'text-emerald-500' },
          pink: { bg: 'bg-pink-50', border: 'border-pink-200', text: 'text-pink-700', icon: 'text-pink-500' }
        }[phase.color];

        return (
          <Card key={phaseKey} className={`${colorClasses.border} border-2 ${phaseComplete ? 'ring-2 ring-green-400' : ''}`}>
            <CardHeader 
              className={`${colorClasses.bg} cursor-pointer`}
              onClick={() => togglePhase(phaseKey)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-full ${colorClasses.bg} flex items-center justify-center`}>
                    <PhaseIcon className={`h-5 w-5 ${colorClasses.icon}`} />
                  </div>
                  <div>
                    <CardTitle className={`flex items-center gap-2 ${colorClasses.text}`}>
                      Phase {phase.phase}: {phase.name}
                      {phaseComplete && <CheckCircle2 className="h-5 w-5 text-green-500" />}
                    </CardTitle>
                    <p className="text-sm text-gray-500">Days {phase.days} • {phaseCompletedCount}/{phaseMilestones.length} complete</p>
                  </div>
                </div>
                {isExpanded ? <ChevronDown className="h-5 w-5 text-gray-400" /> : <ChevronRight className="h-5 w-5 text-gray-400" />}
              </div>
            </CardHeader>
            
            {isExpanded && (
              <CardContent className="pt-4">
                {/* Science Note */}
                <div className={`p-3 ${colorClasses.bg} rounded-lg mb-4`}>
                  <div className="flex items-center gap-2 mb-1">
                    <Beaker className={`h-4 w-4 ${colorClasses.icon}`} />
                    <span className={`font-medium text-sm ${colorClasses.text}`}>The Science</span>
                  </div>
                  <p className="text-sm text-gray-700">{phase.science}</p>
                </div>
                
                {/* Milestones */}
                <div className="space-y-3">
                  {phaseMilestones.map(milestone => {
                    const isChecked = completedMilestones.includes(milestone.day);
                    const isPast = currentDay >= milestone.day;
                    
                    return (
                      <div 
                        key={milestone.day}
                        className={`flex items-start gap-3 p-3 rounded-lg transition-all cursor-pointer ${
                          isChecked 
                            ? 'bg-green-50 border border-green-200' 
                            : isPast 
                              ? 'bg-gray-50 border border-gray-200 hover:bg-gray-100'
                              : 'bg-white border border-gray-100 opacity-60'
                        }`}
                        onClick={() => toggleMilestone(milestone.day)}
                        data-testid={`milestone-day-${milestone.day}`}
                      >
                        {/* Checkbox */}
                        <div className="mt-0.5">
                          {isChecked ? (
                            <CheckCircle2 className="h-5 w-5 text-green-500" />
                          ) : (
                            <Circle className={`h-5 w-5 ${isPast ? 'text-gray-400' : 'text-gray-300'}`} />
                          )}
                        </div>
                        
                        {/* Content */}
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className={milestone.critical ? 'border-amber-300 text-amber-700' : ''}>
                              Day {milestone.day}
                            </Badge>
                            <h4 className={`font-medium ${isChecked ? 'text-green-700 line-through' : 'text-gray-900'}`}>
                              {milestone.title}
                            </h4>
                            {milestone.critical && <Sparkles className="h-4 w-4 text-amber-500" />}
                            {milestone.final && <Gift className="h-4 w-4 text-pink-500" />}
                          </div>
                          <p className={`text-sm mt-1 ${isChecked ? 'text-green-600' : 'text-gray-600'}`}>
                            {milestone.description}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            )}
          </Card>
        );
      })}

      {/* Day 90 Completion Modal */}
      {showShareModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="max-w-md w-full animate-in zoom-in-95">
            <CardContent className="p-6 text-center">
              <div className="w-16 h-16 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <Sparkles className="h-8 w-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Congratulations! 🎉
              </h2>
              <p className="text-gray-600 mb-4">
                You've completed your 12-Week Transformation! Your skin now exhibits the "AURA-GEN" glass finish.
              </p>
              
              {/* Reward */}
              <div className="bg-gradient-to-r from-amber-50 to-yellow-50 p-4 rounded-xl mb-4">
                <Gift className="h-6 w-6 text-amber-500 mx-auto mb-2" />
                <p className="font-medium text-amber-800">Your Reward</p>
                <p className="text-2xl font-bold text-amber-700">20% OFF</p>
                <p className="text-sm text-amber-600">Your next refill order</p>
                <Badge className="mt-2 bg-amber-500">Code: TRANSFORM20</Badge>
              </div>
              
              <div className="flex gap-3">
                <Button 
                  variant="outline" 
                  className="flex-1"
                  onClick={() => setShowShareModal(false)}
                >
                  Close
                </Button>
                <Button 
                  className="flex-1 bg-gradient-to-r from-purple-600 to-pink-500"
                  onClick={() => {
                    // Share functionality
                    if (navigator.share) {
                      navigator.share({
                        title: 'My AURA-GEN Transformation',
                        text: 'I just completed my 12-week skin transformation with AURA-GEN!',
                        url: window.location.origin
                      });
                    }
                    setShowShareModal(false);
                  }}
                >
                  <Share2 className="h-4 w-4 mr-2" />
                  Share Results
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default TransformationCalendar;
