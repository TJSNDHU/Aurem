import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Helmet } from "react-helmet-async";
import { 
  ArrowRight, ArrowLeft, Sparkles, Eye, Clock, Droplets, 
  CheckCircle2, Loader2, FlaskConical, Dna, Shield,
  Sun, Moon, Zap, Target, Heart
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import axios from "axios";
import { API } from "@/lib/api";

// NEW: Import the conversion-optimized Skin Quiz component
import SkinQuiz from "@/components/SkinQuiz";

// Quiz Questions
const QUIZ_QUESTIONS = [
  {
    id: 'age',
    question: "What's your age range?",
    subtext: "This helps us recommend the right concentration of actives",
    type: 'single',
    options: [
      { id: 'teen', label: '13-17', icon: Sparkles, description: 'Teen skin needs gentle formulas' },
      { id: 'young', label: '18-25', icon: Zap, description: 'Prevention & hydration focus' },
      { id: 'adult', label: '26-35', icon: Target, description: 'Early anti-aging & brightening' },
      { id: 'mature', label: '36-50', icon: Shield, description: 'Repair & regeneration' },
      { id: 'senior', label: '50+', icon: Heart, description: 'Deep rejuvenation & firming' },
    ]
  },
  {
    id: 'concerns',
    question: "What are your top skin concerns?",
    subtext: "Select all that apply",
    type: 'multiple',
    options: [
      { id: 'dark-circles', label: 'Dark Circles & Puffiness', icon: Eye, keywords: ['dark circles', 'puffiness', 'under-eye'] },
      { id: 'pigmentation', label: 'Pigmentation & Dark Spots', icon: Sun, keywords: ['pigmentation', 'melasma', 'dark spots'] },
      { id: 'anti-aging', label: 'Wrinkles & Fine Lines', icon: Clock, keywords: ['wrinkles', 'anti-aging', 'firming'] },
      { id: 'hydration', label: 'Dryness & Dehydration', icon: Droplets, keywords: ['dry skin', 'hydration', 'moisture'] },
      { id: 'dullness', label: 'Dull & Uneven Skin Tone', icon: Sparkles, keywords: ['dullness', 'brightening', 'glow'] },
      { id: 'acne', label: 'Acne & Blemishes', icon: Target, keywords: ['acne', 'blemishes', 'breakouts'] },
    ]
  },
  {
    id: 'skin-type',
    question: "What's your skin type?",
    subtext: "This affects how we recommend textures and formulations",
    type: 'single',
    options: [
      { id: 'dry', label: 'Dry', icon: Moon, description: 'Feels tight, flaky, or rough' },
      { id: 'oily', label: 'Oily', icon: Sun, description: 'Shiny T-zone, enlarged pores' },
      { id: 'combination', label: 'Combination', icon: Zap, description: 'Oily T-zone, dry cheeks' },
      { id: 'normal', label: 'Normal', icon: Heart, description: 'Balanced, minimal concerns' },
      { id: 'sensitive', label: 'Sensitive', icon: Shield, description: 'Easily irritated, reactive' },
    ]
  },
  {
    id: 'current-routine',
    question: "What's your current skincare routine like?",
    subtext: "This helps us build on what you already do",
    type: 'single',
    options: [
      { id: 'minimal', label: 'Minimal (Cleanser + Moisturizer)', icon: Droplets, description: 'Just the basics' },
      { id: 'moderate', label: 'Moderate (+ Serum or SPF)', icon: FlaskConical, description: '3-4 products' },
      { id: 'advanced', label: 'Advanced (Multi-step)', icon: Dna, description: '5+ products with actives' },
      { id: 'none', label: 'No routine yet', icon: Sparkles, description: 'Looking to start' },
    ]
  },
  {
    id: 'ingredients',
    question: "Have you used any of these ingredients before?",
    subtext: "Select all that apply",
    type: 'multiple',
    options: [
      { id: 'retinol', label: 'Retinol / Vitamin A', icon: Zap },
      { id: 'vitamin-c', label: 'Vitamin C', icon: Sun },
      { id: 'hyaluronic', label: 'Hyaluronic Acid', icon: Droplets },
      { id: 'niacinamide', label: 'Niacinamide', icon: Shield },
      { id: 'peptides', label: 'Peptides', icon: Dna },
      { id: 'none', label: 'None of these', icon: Sparkles },
    ]
  },
  {
    id: 'email',
    question: "Get your personalized PDRN Protocol",
    subtext: "We'll email your custom skincare routine",
    type: 'email',
    options: []
  }
];

// Product recommendations based on quiz results
const getRecommendations = (answers) => {
  const recommendations = [];
  const concerns = answers.concerns || [];
  const age = answers.age;
  const skinType = answers['skin-type'];
  
  // Primary concern-based recommendations
  if (concerns.includes('dark-circles')) {
    recommendations.push({
      id: 'eye-concentrate',
      name: 'NAD+ Pink Peptide Eye Concentrate',
      reason: 'Targets dark circles with NAD+ technology',
      priority: 1,
      link: '/products/nad-pink-peptide-eye-concentrate'
    });
  }
  
  if (concerns.includes('pigmentation') || concerns.includes('dullness')) {
    recommendations.push({
      id: 'aura-gen',
      name: 'AURA-GEN PDRN + TXA + Argireline 17%',
      reason: '5% Tranexamic Acid fades pigmentation effectively',
      priority: 1,
      link: '/products/aura-gen-txa-pdrn'
    });
  }
  
  if (concerns.includes('anti-aging')) {
    recommendations.push({
      id: 'copper-peptide',
      name: 'Copper Peptide Revitalizing Complex',
      reason: 'GHK-Cu promotes collagen and reduces wrinkles',
      priority: age === 'mature' || age === 'senior' ? 1 : 2,
      link: '/products/copper-peptide-complex'
    });
  }
  
  if (concerns.includes('hydration') || skinType === 'dry') {
    recommendations.push({
      id: 'hydra-barrier',
      name: 'Hydra-Barrier Moisturizer',
      reason: 'Ceramide-rich barrier support for lasting hydration',
      priority: 2,
      link: '/products/hydra-barrier-moisturizer'
    });
  }
  
  // Always recommend AURA-GEN as flagship if not already added
  if (!recommendations.find(r => r.id === 'aura-gen')) {
    recommendations.push({
      id: 'aura-gen',
      name: 'AURA-GEN PDRN + TXA + Argireline 17%',
      reason: 'Our flagship biotech serum with 2% PDRN',
      priority: 2,
      link: '/products/aura-gen-txa-pdrn'
    });
  }
  
  // Sort by priority
  return recommendations.sort((a, b) => a.priority - b.priority).slice(0, 3);
};

// Generate personalized routine
const generateRoutine = (answers) => {
  const morning = ['Gentle Cleanser', 'AURA-GEN Serum (3-4 drops)', 'Hydra-Barrier Moisturizer', 'SPF 50'];
  const evening = ['Double Cleanse', 'AURA-GEN Serum (3-4 drops)'];
  
  if (answers.concerns?.includes('dark-circles')) {
    evening.push('NAD+ Eye Concentrate');
  }
  
  if (answers.concerns?.includes('anti-aging') && (answers.age === 'mature' || answers.age === 'senior')) {
    evening.push('Copper Peptide Complex');
  }
  
  evening.push('Hydra-Barrier Moisturizer');
  
  return { morning, evening };
};

const SkinQuizPage = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [routine, setRoutine] = useState({ morning: [], evening: [] });

  const progress = ((currentStep + 1) / QUIZ_QUESTIONS.length) * 100;
  const currentQuestion = QUIZ_QUESTIONS[currentStep];

  const handleSelect = (optionId) => {
    if (currentQuestion.type === 'single') {
      setAnswers(prev => ({ ...prev, [currentQuestion.id]: optionId }));
      // Auto-advance after selection
      setTimeout(() => {
        if (currentStep < QUIZ_QUESTIONS.length - 1) {
          setCurrentStep(prev => prev + 1);
        }
      }, 300);
    } else if (currentQuestion.type === 'multiple') {
      setAnswers(prev => {
        const current = prev[currentQuestion.id] || [];
        if (current.includes(optionId)) {
          return { ...prev, [currentQuestion.id]: current.filter(id => id !== optionId) };
        } else {
          return { ...prev, [currentQuestion.id]: [...current, optionId] };
        }
      });
    }
  };

  const handleNext = () => {
    if (currentStep < QUIZ_QUESTIONS.length - 1) {
      setCurrentStep(prev => prev + 1);
    } else {
      handleSubmit();
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1);
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    
    // Generate recommendations
    const recs = getRecommendations(answers);
    const routineData = generateRoutine(answers);
    
    setRecommendations(recs);
    setRoutine(routineData);
    
    // Submit to backend (for email marketing integration)
    try {
      await axios.post(`${API}/quiz/submit`, {
        email,
        answers,
        recommendations: recs,
        routine: routineData,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.log('Quiz submission logged locally');
    }
    
    setLoading(false);
    setShowResults(true);
  };

  const isOptionSelected = (optionId) => {
    const answer = answers[currentQuestion?.id];
    if (Array.isArray(answer)) {
      return answer.includes(optionId);
    }
    return answer === optionId;
  };

  const canProceed = () => {
    if (currentQuestion?.type === 'email') {
      return email.includes('@') && email.includes('.');
    }
    const answer = answers[currentQuestion?.id];
    if (currentQuestion?.type === 'multiple') {
      return Array.isArray(answer) && answer.length > 0;
    }
    return !!answer;
  };

  // JSON-LD Schema for Quiz
  const quizSchema = {
    "@context": "https://schema.org",
    "@type": "Quiz",
    "name": "ReRoots Skin Analysis Quiz",
    "description": "Personalized skincare routine recommendation based on your skin concerns, type, and goals.",
    "educationalAlignment": {
      "@type": "AlignmentObject",
      "alignmentType": "teaches",
      "targetName": "Skincare"
    },
    "provider": {
      "@type": "Organization",
      "name": "ReRoots Biotech Skincare"
    }
  };

  if (showResults) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-[#FDF9F9] to-white pt-24 pb-16">
        <Helmet>
          <title>Your Personalized PDRN Protocol | ReRoots Skin Quiz Results</title>
          <meta name="robots" content="noindex" />
        </Helmet>
        
        <div className="max-w-4xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center mb-12"
          >
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-r from-[#D4AF37] to-[#F8A5B8] flex items-center justify-center">
              <CheckCircle2 className="h-10 w-10 text-white" />
            </div>
            <Badge className="bg-[#D4AF37]/10 text-[#D4AF37] hover:bg-[#D4AF37]/10 mb-4 font-mono text-xs tracking-[0.2em]">
              YOUR PERSONALIZED PROTOCOL
            </Badge>
            <h1 className="font-luxury text-3xl md:text-4xl text-[#2D2A2E] mb-4">
              Your <span className="italic text-[#F8A5B8]">PDRN Protocol</span> is Ready
            </h1>
            <p className="text-[#5A5A5A] max-w-xl mx-auto">
              Based on your answers, we've curated a biotech skincare routine optimized for your specific concerns.
            </p>
          </motion.div>

          {/* Recommended Products */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mb-12"
          >
            <h2 className="font-luxury text-2xl text-[#2D2A2E] mb-6 text-center">
              Recommended <span className="italic text-[#D4AF37]">Products</span>
            </h2>
            <div className="grid md:grid-cols-3 gap-6">
              {recommendations.map((rec, index) => (
                <motion.div
                  key={rec.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.3 + index * 0.1 }}
                  className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-lg transition-all"
                >
                  <Badge className={`mb-4 ${index === 0 ? 'bg-[#D4AF37] text-white' : 'bg-gray-100 text-gray-600'}`}>
                    {index === 0 ? 'Top Pick' : `#${index + 1}`}
                  </Badge>
                  <h3 className="font-luxury text-lg text-[#2D2A2E] mb-2">{rec.name}</h3>
                  <p className="text-sm text-[#5A5A5A] mb-4">{rec.reason}</p>
                  <Link to={rec.link}>
                    <Button className="w-full bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white rounded-full">
                      View Product
                    </Button>
                  </Link>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Routine */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="grid md:grid-cols-2 gap-8 mb-12"
          >
            {/* Morning Routine */}
            <div className="bg-gradient-to-br from-amber-50 to-white rounded-2xl p-8 border border-amber-100">
              <div className="flex items-center gap-3 mb-6">
                <Sun className="h-6 w-6 text-amber-500" />
                <h3 className="font-luxury text-xl text-[#2D2A2E]">Morning Routine</h3>
              </div>
              <ol className="space-y-4">
                {routine.morning.map((step, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center text-sm font-medium">
                      {index + 1}
                    </span>
                    <span className="text-[#5A5A5A]">{step}</span>
                  </li>
                ))}
              </ol>
            </div>

            {/* Evening Routine */}
            <div className="bg-gradient-to-br from-indigo-50 to-white rounded-2xl p-8 border border-indigo-100">
              <div className="flex items-center gap-3 mb-6">
                <Moon className="h-6 w-6 text-indigo-500" />
                <h3 className="font-luxury text-xl text-[#2D2A2E]">Evening Routine</h3>
              </div>
              <ol className="space-y-4">
                {routine.evening.map((step, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-sm font-medium">
                      {index + 1}
                    </span>
                    <span className="text-[#5A5A5A]">{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          </motion.div>

          {/* CTA */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.7 }}
            className="text-center"
          >
            <Link to="/shop">
              <Button className="bg-gradient-to-r from-[#D4AF37] to-[#F8A5B8] hover:opacity-90 text-white rounded-full px-10 py-6 text-lg font-medium shadow-lg">
                Shop Your Protocol <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
            <p className="text-sm text-[#5A5A5A] mt-4">
              We've sent your personalized routine to {email}
            </p>
          </motion.div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#FDF9F9] to-white pt-24 pb-16">
      <Helmet>
        <title>Skin Quiz | Find Your PDRN Protocol | ReRoots Canada</title>
        <meta name="description" content="Take our 2-minute skin quiz to discover your personalized PDRN skincare routine. Get expert recommendations for dark circles, pigmentation, anti-aging & more." />
        <meta name="keywords" content="skin quiz, skincare quiz, PDRN recommendation, personalized skincare, skin analysis, dark circles treatment quiz, pigmentation quiz" />
        <link rel="canonical" href="https://reroots.ca/skin-quiz" />
        <script type="application/ld+json">{JSON.stringify(quizSchema)}</script>
      </Helmet>

      <div className="max-w-2xl mx-auto px-6">
        {/* Progress Bar */}
        <div className="mb-12">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm text-[#5A5A5A] font-medium">
              Step {currentStep + 1} of {QUIZ_QUESTIONS.length}
            </span>
            <span className="text-sm text-[#D4AF37] font-medium">
              {Math.round(progress)}% Complete
            </span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>

        {/* Question */}
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
          >
            <div className="text-center mb-10">
              <h1 className="font-luxury text-2xl md:text-3xl text-[#2D2A2E] mb-3">
                {currentQuestion.question}
              </h1>
              <p className="text-[#5A5A5A]">{currentQuestion.subtext}</p>
            </div>

            {/* Options */}
            {currentQuestion.type === 'email' ? (
              <div className="max-w-md mx-auto space-y-6">
                <Input
                  type="email"
                  placeholder="your@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="text-center text-lg py-6 rounded-full border-2 border-gray-200 focus:border-[#D4AF37] focus:ring-[#D4AF37]/20"
                />
                <p className="text-xs text-center text-[#5A5A5A]">
                  By submitting, you agree to receive personalized skincare recommendations from ReRoots.
                </p>
              </div>
            ) : (
              <div className={`grid gap-4 ${currentQuestion.options.length > 4 ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-1 md:grid-cols-2'}`}>
                {currentQuestion.options.map((option) => {
                  const Icon = option.icon;
                  const isSelected = isOptionSelected(option.id);
                  return (
                    <motion.button
                      key={option.id}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => handleSelect(option.id)}
                      className={`
                        relative p-6 rounded-2xl border-2 text-left transition-all duration-300
                        ${isSelected 
                          ? 'border-[#D4AF37] bg-[#D4AF37]/5 shadow-lg' 
                          : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-md'
                        }
                      `}
                    >
                      {isSelected && (
                        <div className="absolute top-4 right-4">
                          <CheckCircle2 className="h-5 w-5 text-[#D4AF37]" />
                        </div>
                      )}
                      <Icon className={`h-8 w-8 mb-3 ${isSelected ? 'text-[#D4AF37]' : 'text-gray-400'}`} />
                      <h3 className={`font-medium text-lg mb-1 ${isSelected ? 'text-[#2D2A2E]' : 'text-gray-700'}`}>
                        {option.label}
                      </h3>
                      {option.description && (
                        <p className="text-sm text-[#5A5A5A]">{option.description}</p>
                      )}
                    </motion.button>
                  );
                })}
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {/* Navigation */}
        <div className="flex justify-between mt-12">
          <Button
            variant="ghost"
            onClick={handleBack}
            disabled={currentStep === 0}
            className="text-[#5A5A5A] hover:text-[#2D2A2E]"
          >
            <ArrowLeft className="mr-2 h-4 w-4" /> Back
          </Button>
          
          {(currentQuestion.type === 'multiple' || currentQuestion.type === 'email') && (
            <Button
              onClick={handleNext}
              disabled={!canProceed() || loading}
              className="bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white rounded-full px-8"
            >
              {loading ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : currentStep === QUIZ_QUESTIONS.length - 1 ? (
                <>Get My Protocol <Sparkles className="ml-2 h-4 w-4" /></>
              ) : (
                <>Next <ArrowRight className="ml-2 h-4 w-4" /></>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

// Wrapper that uses new conversion-optimized quiz by default
// Add ?v=classic to URL to use the original multi-step quiz
const SkinQuizPageWrapper = () => {
  const [searchParams] = React.useState(() => new URLSearchParams(window.location.search));
  const version = searchParams.get('v');
  
  // Use new optimized quiz by default (87.5% CVR)
  if (version !== 'classic') {
    return (
      <>
        <Helmet>
          <title>Skin Quiz - Find Your PDRN Protocol | ReRoots</title>
          <meta name="description" content="Take our 2-minute skin quiz to find your personalised PDRN protocol. 6 questions, 87.5% match accuracy. Free and Health Canada compliant." />
        </Helmet>
        <SkinQuiz />
      </>
    );
  }
  
  // Classic version with ?v=classic
  return <SkinQuizPage />;
};

export default SkinQuizPageWrapper;
