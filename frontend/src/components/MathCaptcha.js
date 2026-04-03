import React, { useState, useEffect, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { RefreshCw, ShieldCheck } from "lucide-react";

const MathCaptcha = ({ onVerify, className = "" }) => {
  const [num1, setNum1] = useState(0);
  const [num2, setNum2] = useState(0);
  const [operator, setOperator] = useState("+");
  const [userAnswer, setUserAnswer] = useState("");
  const [isVerified, setIsVerified] = useState(false);
  const [error, setError] = useState(false);
  
  // Generate a new math problem
  const generateProblem = useCallback(() => {
    const operators = ["+", "-", "×"];
    const op = operators[Math.floor(Math.random() * operators.length)];
    
    let n1, n2;
    
    if (op === "+") {
      n1 = Math.floor(Math.random() * 10) + 1; // 1-10
      n2 = Math.floor(Math.random() * 10) + 1; // 1-10
    } else if (op === "-") {
      n1 = Math.floor(Math.random() * 10) + 5; // 5-14
      n2 = Math.floor(Math.random() * n1); // 0 to n1 (ensure positive result)
    } else {
      n1 = Math.floor(Math.random() * 5) + 1; // 1-5
      n2 = Math.floor(Math.random() * 5) + 1; // 1-5
    }
    
    setNum1(n1);
    setNum2(n2);
    setOperator(op);
    setUserAnswer("");
    setIsVerified(false);
    setError(false);
    onVerify(false);
  }, [onVerify]);
  
  // Initialize on mount
  useEffect(() => {
    generateProblem();
  }, [generateProblem]);
  
  // Calculate correct answer
  const getCorrectAnswer = () => {
    switch (operator) {
      case "+": return num1 + num2;
      case "-": return num1 - num2;
      case "×": return num1 * num2;
      default: return num1 + num2;
    }
  };
  
  // Verify the answer
  const handleVerify = () => {
    const correct = getCorrectAnswer();
    const userNum = parseInt(userAnswer, 10);
    
    if (userNum === correct) {
      setIsVerified(true);
      setError(false);
      onVerify(true);
    } else {
      setError(true);
      setIsVerified(false);
      onVerify(false);
      // Generate new problem after wrong answer
      setTimeout(() => {
        generateProblem();
      }, 1500);
    }
  };
  
  // Auto-verify when user types correct answer
  useEffect(() => {
    if (userAnswer && !isVerified) {
      const correct = getCorrectAnswer();
      const userNum = parseInt(userAnswer, 10);
      
      if (userNum === correct) {
        setIsVerified(true);
        setError(false);
        onVerify(true);
      }
    }
  }, [userAnswer, isVerified, onVerify, num1, num2, operator]);
  
  if (isVerified) {
    return (
      <div 
        className={`flex items-center gap-3 p-3 rounded-lg ${className}`}
        style={{
          background: "rgba(34, 197, 94, 0.1)",
          border: "1px solid rgba(34, 197, 94, 0.3)"
        }}
      >
        <ShieldCheck className="w-5 h-5 text-green-500" />
        <span className="text-green-400 text-sm font-medium">Verified - You're human! ✓</span>
      </div>
    );
  }
  
  return (
    <div className={`space-y-3 ${className}`}>
      <div 
        className="p-4 rounded-lg"
        style={{
          background: "rgba(255, 255, 255, 0.03)",
          border: error ? "1px solid rgba(239, 68, 68, 0.5)" : "1px solid rgba(255, 255, 255, 0.1)"
        }}
      >
        <div className="flex items-center justify-between mb-3">
          <span className="text-white/50 text-xs uppercase tracking-wider">Quick verification</span>
          <button
            type="button"
            onClick={generateProblem}
            className="text-white/30 hover:text-white/60 transition-colors"
            title="New problem"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Math Problem Display */}
          <div 
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg"
            style={{ background: "rgba(0, 0, 0, 0.3)" }}
          >
            <span className="text-white text-xl font-mono font-bold">{num1}</span>
            <span className="text-[#D4AF37] text-xl font-mono">{operator}</span>
            <span className="text-white text-xl font-mono font-bold">{num2}</span>
            <span className="text-white/50 text-xl font-mono">=</span>
            <span className="text-[#D4AF37] text-xl font-mono">?</span>
          </div>
          
          {/* Answer Input */}
          <Input
            type="number"
            placeholder="?"
            value={userAnswer}
            onChange={(e) => {
              setUserAnswer(e.target.value);
              setError(false);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleVerify();
              }
            }}
            className={`w-20 h-12 text-center text-lg font-mono bg-white/5 border-white/10 text-white placeholder:text-white/30 rounded-lg focus:border-[#D4AF37] focus:ring-[#D4AF37]/20 ${
              error ? 'border-red-500 shake-animation' : ''
            }`}
            data-testid="captcha-input"
          />
        </div>
        
        {error && (
          <p className="text-red-400 text-xs mt-2 text-center">
            Incorrect answer. Try the new problem.
          </p>
        )}
      </div>
      
      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-5px); }
          75% { transform: translateX(5px); }
        }
        .shake-animation {
          animation: shake 0.3s ease-in-out;
        }
      `}</style>
    </div>
  );
};

export default MathCaptcha;
