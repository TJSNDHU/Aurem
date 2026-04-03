import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Lock, Unlock, Gift, Users, Sparkles, Copy, Check } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * MilestoneProgress - Shows the 10-referral unlock progress
 * Used on: Partner Dashboard, Founding Member Success Page, User Profile
 */
const MilestoneProgress = ({ 
  referralCode, 
  compact = false, 
  showShareLink = true,
  onUnlock = null 
}) => {
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (referralCode) {
      loadProgress();
    }
  }, [referralCode]);

  const loadProgress = async () => {
    try {
      const res = await axios.get(`${API}/milestone/progress/${referralCode}`);
      setProgress(res.data);
      
      // Callback when milestone is unlocked
      if (res.data.unlocked && onUnlock) {
        onUnlock(res.data);
      }
    } catch (err) {
      console.error('Failed to load milestone progress:', err);
    }
    setLoading(false);
  };

  const copyShareLink = () => {
    const link = `${window.location.origin}/Bio-Age-Repair-Scan?ref=${referralCode}`;
    navigator.clipboard.writeText(link);
    setCopied(true);
    toast.success('Referral link copied!');
    setTimeout(() => setCopied(false), 2000);
  };

  const copyUnlockCode = () => {
    if (progress?.unlock_code) {
      navigator.clipboard.writeText(progress.unlock_code);
      toast.success('Discount code copied!');
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse bg-gray-100 rounded-xl h-32" />
    );
  }

  if (!progress) {
    return null;
  }

  // Compact version for sidebars/small spaces
  if (compact) {
    return (
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-lg p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Unlock Progress</span>
          <Badge className={progress.unlocked ? 'bg-green-500' : 'bg-amber-500'}>
            {progress.count}/{progress.threshold}
          </Badge>
        </div>
        <Progress value={progress.progress_percent} className="h-2" />
        {progress.unlocked ? (
          <p className="text-xs text-green-600 mt-2 flex items-center gap-1">
            <Unlock className="w-3 h-3" />
            30% Discount Unlocked!
          </p>
        ) : (
          <p className="text-xs text-gray-500 mt-2">
            {progress.remaining} more to unlock 30% OFF
          </p>
        )}
      </div>
    );
  }

  // Full version - Sleek Biotech Branding
  return (
    <Card className={`overflow-hidden relative ${
      progress.unlocked 
        ? 'border-[#00C853]/30 bg-gradient-to-br from-[#E8F5E9] via-white to-[#F1F8E9]' 
        : 'border-[#F8A5B8]/30 bg-gradient-to-br from-[#FFF5F7] via-white to-[#FFF0F3]'
    }`}>
      {/* Biotech Pattern Overlay */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute inset-0" style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, ${progress.unlocked ? '#00C853' : '#F8A5B8'} 1px, transparent 0)`,
          backgroundSize: '24px 24px'
        }} />
      </div>
      
      <CardHeader className="pb-2 relative">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            {progress.unlocked ? (
              <>
                <div className="p-1.5 rounded-lg bg-green-100">
                  <Unlock className="w-4 h-4 text-green-600" />
                </div>
                <span className="text-green-800">30% Discount Unlocked!</span>
              </>
            ) : (
              <>
                <div className="p-1.5 rounded-lg bg-[#F8A5B8]/20">
                  <Lock className="w-4 h-4 text-[#E91E63]" />
                </div>
                <span className="text-[#2D2A2E]">Unlock 30% Lifetime Discount</span>
              </>
            )}
          </CardTitle>
          {progress.unlocked && (
            <Badge className="bg-gradient-to-r from-green-500 to-emerald-500 text-white shadow-sm">
              <Sparkles className="w-3 h-3 mr-1" />
              Active
            </Badge>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4 relative">
        {/* Progress Section */}
        <div>
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm text-gray-600 font-medium">Verified Referrals</span>
            <span className="text-2xl font-bold text-[#2D2A2E]">
              {progress.count} <span className="text-gray-400 text-lg font-normal">/ {progress.threshold}</span>
            </span>
          </div>
          
          {/* Sleek Progress Bar */}
          <div className="relative">
            <div className="h-3 rounded-full bg-gray-100 overflow-hidden shadow-inner">
              <div 
                className={`h-full rounded-full transition-all duration-700 ease-out ${
                  progress.unlocked 
                    ? 'bg-gradient-to-r from-green-400 to-emerald-500' 
                    : 'bg-gradient-to-r from-[#F8A5B8] to-[#E91E63]'
                }`}
                style={{ width: `${progress.progress_percent}%` }}
              />
            </div>
            {/* Milestone Markers */}
            <div className="absolute top-0 left-0 w-full h-3 flex justify-between px-0.5">
              {[...Array(10)].map((_, i) => (
                <div 
                  key={i}
                  className={`w-0.5 h-3 ${i < progress.count ? 'bg-white/50' : 'bg-gray-300/50'}`}
                />
              ))}
            </div>
          </div>
          
          {!progress.unlocked && (
            <p className="text-sm text-gray-500 mt-3 flex items-center gap-2">
              <div className="p-1 rounded bg-[#F8A5B8]/10">
                <Users className="w-3 h-3 text-[#E91E63]" />
              </div>
              <span>{progress.remaining} more verified referral{progress.remaining !== 1 ? 's' : ''} to unlock <span className="font-semibold text-[#2D2A2E]">$70 Founding Price</span></span>
            </p>
          )}
        </div>

        {/* Unlocked State */}
        {progress.unlocked && progress.unlock_code && (
          <div className="bg-white rounded-lg p-4 border border-green-200">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Your Exclusive Code</p>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-mono font-bold text-green-600 tracking-wider">
                {progress.unlock_code}
              </span>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={copyUnlockCode}
                className="text-green-600 hover:text-green-700"
              >
                <Copy className="w-4 h-4" />
              </Button>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div className="bg-green-50 rounded p-2">
                <p className="font-medium text-green-700">For You</p>
                <p className="text-green-600 text-xs">30% off all orders forever</p>
              </div>
              <div className="bg-green-50 rounded p-2">
                <p className="font-medium text-green-700">For Friends</p>
                <p className="text-green-600 text-xs">Share code for 30% off</p>
              </div>
            </div>
          </div>
        )}

        {/* Share Link Section */}
        {showShareLink && !progress.unlocked && (
          <div className="bg-white/70 backdrop-blur rounded-xl p-4 border border-gray-100 shadow-sm">
            <p className="text-sm font-semibold text-[#2D2A2E] mb-2 flex items-center gap-2">
              <div className="p-1 rounded bg-[#F8A5B8]/10">
                <Gift className="w-3 h-3 text-[#E91E63]" />
              </div>
              How to Unlock
            </p>
            <p className="text-sm text-gray-600 mb-3 leading-relaxed">
              Share your unique link. When friends complete the <span className="font-medium text-[#2D2A2E]">Bio-Age Scan</span>, it counts as a verified referral!
            </p>
            <Button 
              onClick={copyShareLink}
              className="w-full bg-gradient-to-r from-[#F8A5B8] to-[#E91E63] hover:from-[#E91E63] hover:to-[#C2185B] text-white shadow-md transition-all duration-300 hover:shadow-lg"
              data-testid="copy-referral-link-btn"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  Link Copied!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4 mr-2" />
                  Copy Your Referral Link
                </>
              )}
            </Button>
          </div>
        )}

        {/* Requirements Note */}
        {!progress.unlocked && (
          <p className="text-xs text-gray-400 text-center font-medium">
            Referrals must verify WhatsApp + complete Bio-Age Scan to count
          </p>
        )}
      </CardContent>
    </Card>
  );
};

export default MilestoneProgress;
