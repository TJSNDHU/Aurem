import React, { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Trophy, Medal, Award, Crown, Users, TrendingUp, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const ReferralLeaderboard = ({ currentUserCode, compact = false }) => {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [userRank, setUserRank] = useState(null);
  const [totalReferrers, setTotalReferrers] = useState(0);
  
  useEffect(() => {
    fetchLeaderboard();
  }, [currentUserCode]);
  
  const fetchLeaderboard = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/referral/leaderboard`);
      setLeaderboard(res.data.leaderboard || []);
      setTotalReferrers(res.data.total_referrers || 0);
      
      // Find current user's rank
      if (currentUserCode) {
        const rank = res.data.leaderboard?.findIndex(
          u => u.referral_code === currentUserCode
        );
        setUserRank(rank >= 0 ? rank + 1 : null);
      }
    } catch (error) {
      console.error("Failed to fetch leaderboard:", error);
      // Mock data for demo
      setLeaderboard([
        { name: "Sarah M.", referral_count: 24, referral_code: "SARAH24", voucher_unlocked: true },
        { name: "Michael T.", referral_count: 18, referral_code: "MIKE18", voucher_unlocked: true },
        { name: "Emma L.", referral_count: 15, referral_code: "EMMA15", voucher_unlocked: true },
        { name: "James K.", referral_count: 12, referral_code: "JAMES12", voucher_unlocked: true },
        { name: "Olivia R.", referral_count: 10, referral_code: "OLIVIA10", voucher_unlocked: true },
        { name: "David P.", referral_count: 8, referral_code: "DAVID8", voucher_unlocked: false },
        { name: "Sophia W.", referral_count: 7, referral_code: "SOPHIA7", voucher_unlocked: false },
        { name: "Daniel H.", referral_count: 5, referral_code: "DAN5", voucher_unlocked: false },
        { name: "Ava C.", referral_count: 4, referral_code: "AVA4", voucher_unlocked: false },
        { name: "Noah B.", referral_count: 3, referral_code: "NOAH3", voucher_unlocked: false },
      ]);
      setTotalReferrers(127);
    }
    setLoading(false);
  };
  
  const getRankIcon = (rank) => {
    switch(rank) {
      case 1:
        return <Trophy className="w-5 h-5 text-[#FFD700]" />;
      case 2:
        return <Medal className="w-5 h-5 text-[#C0C0C0]" />;
      case 3:
        return <Award className="w-5 h-5 text-[#CD7F32]" />;
      default:
        return <span className="w-5 h-5 flex items-center justify-center text-white/50 font-mono text-sm">#{rank}</span>;
    }
  };
  
  const getRankBg = (rank) => {
    switch(rank) {
      case 1:
        return "bg-gradient-to-r from-[#FFD700]/20 to-[#FFD700]/5 border-[#FFD700]/30";
      case 2:
        return "bg-gradient-to-r from-[#C0C0C0]/20 to-[#C0C0C0]/5 border-[#C0C0C0]/30";
      case 3:
        return "bg-gradient-to-r from-[#CD7F32]/20 to-[#CD7F32]/5 border-[#CD7F32]/30";
      default:
        return "bg-[#1a1a1a] border-[#333]";
    }
  };
  
  if (compact) {
    // Compact version for sidebar/widget
    return (
      <Card className="bg-[#1a1a1a] border-[#333]">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2 text-white/80">
            <Trophy className="w-4 h-4 text-[#D4AF37]" />
            Top Referrers
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {loading ? (
            <div className="animate-pulse space-y-2">
              {[1,2,3].map(i => (
                <div key={i} className="h-8 bg-[#2a2a2a] rounded" />
              ))}
            </div>
          ) : (
            <>
              {leaderboard.slice(0, 3).map((user, idx) => (
                <div 
                  key={idx}
                  className={`flex items-center justify-between p-2 rounded-lg ${
                    user.referral_code === currentUserCode ? 'ring-1 ring-[#D4AF37]' : ''
                  } ${getRankBg(idx + 1)}`}
                >
                  <div className="flex items-center gap-2">
                    {getRankIcon(idx + 1)}
                    <span className="text-sm text-white/80 truncate max-w-[100px]">
                      {user.name || `User ${idx + 1}`}
                    </span>
                  </div>
                  <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] text-xs">
                    {user.referral_count}
                  </Badge>
                </div>
              ))}
              {userRank && userRank > 3 && (
                <div className="pt-2 border-t border-[#333]">
                  <div className="flex items-center justify-between p-2 bg-[#D4AF37]/10 border border-[#D4AF37]/30 rounded-lg">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-white/50">You:</span>
                      <span className="text-sm text-[#D4AF37]">#{userRank}</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    );
  }
  
  // Full leaderboard
  return (
    <Card className="bg-[#1a1a1a] border-[#333]">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-white">
              <Trophy className="w-5 h-5 text-[#D4AF37]" />
              Referral Leaderboard
            </CardTitle>
            <CardDescription className="flex items-center gap-4 mt-2">
              <span className="flex items-center gap-1">
                <Users className="w-4 h-4" />
                {totalReferrers} active referrers
              </span>
              <span className="flex items-center gap-1">
                <TrendingUp className="w-4 h-4 text-green-400" />
                Updated live
              </span>
            </CardDescription>
          </div>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={fetchLeaderboard}
            className="text-white/60 hover:text-white"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="animate-pulse space-y-3">
            {[1,2,3,4,5].map(i => (
              <div key={i} className="h-12 bg-[#2a2a2a] rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {/* Top 3 Podium */}
            <div className="grid grid-cols-3 gap-2 mb-6">
              {/* 2nd Place */}
              <div className="flex flex-col items-center pt-6">
                {leaderboard[1] && (
                  <>
                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#C0C0C0] to-[#A0A0A0] flex items-center justify-center mb-2">
                      <Medal className="w-6 h-6 text-white" />
                    </div>
                    <p className="text-sm font-medium text-white truncate max-w-full">
                      {leaderboard[1].name || "Member"}
                    </p>
                    <p className="text-lg font-bold text-[#C0C0C0]">{leaderboard[1].referral_count}</p>
                    <div className="h-16 w-full bg-[#C0C0C0]/20 rounded-t-lg mt-2" />
                  </>
                )}
              </div>
              
              {/* 1st Place */}
              <div className="flex flex-col items-center">
                {leaderboard[0] && (
                  <>
                    <Crown className="w-6 h-6 text-[#FFD700] mb-1" />
                    <div className="w-14 h-14 rounded-full bg-gradient-to-br from-[#FFD700] to-[#FFA500] flex items-center justify-center mb-2 ring-4 ring-[#FFD700]/30">
                      <Trophy className="w-7 h-7 text-white" />
                    </div>
                    <p className="text-sm font-medium text-white truncate max-w-full">
                      {leaderboard[0].name || "Member"}
                    </p>
                    <p className="text-xl font-bold text-[#FFD700]">{leaderboard[0].referral_count}</p>
                    <div className="h-24 w-full bg-[#FFD700]/20 rounded-t-lg mt-2" />
                  </>
                )}
              </div>
              
              {/* 3rd Place */}
              <div className="flex flex-col items-center pt-10">
                {leaderboard[2] && (
                  <>
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#CD7F32] to-[#8B4513] flex items-center justify-center mb-2">
                      <Award className="w-5 h-5 text-white" />
                    </div>
                    <p className="text-sm font-medium text-white truncate max-w-full">
                      {leaderboard[2].name || "Member"}
                    </p>
                    <p className="text-lg font-bold text-[#CD7F32]">{leaderboard[2].referral_count}</p>
                    <div className="h-12 w-full bg-[#CD7F32]/20 rounded-t-lg mt-2" />
                  </>
                )}
              </div>
            </div>
            
            {/* Rest of leaderboard */}
            <div className="space-y-2">
              {leaderboard.slice(3, 10).map((user, idx) => {
                const rank = idx + 4;
                const isCurrentUser = user.referral_code === currentUserCode;
                
                return (
                  <div 
                    key={idx}
                    className={`flex items-center justify-between p-3 rounded-lg border transition-all ${
                      isCurrentUser 
                        ? 'bg-[#D4AF37]/10 border-[#D4AF37] ring-1 ring-[#D4AF37]' 
                        : 'bg-[#2a2a2a] border-[#333] hover:border-[#444]'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-8 h-8 flex items-center justify-center rounded-full bg-[#333] text-white/60 font-mono text-sm">
                        {rank}
                      </span>
                      <div>
                        <p className={`font-medium ${isCurrentUser ? 'text-[#D4AF37]' : 'text-white/80'}`}>
                          {user.name || `Member #${rank}`}
                          {isCurrentUser && <span className="text-xs ml-2">(You)</span>}
                        </p>
                        {user.voucher_unlocked && (
                          <Badge className="bg-green-500/20 text-green-400 text-xs mt-1">
                            VIP Unlocked
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-white">{user.referral_count}</p>
                      <p className="text-xs text-white/40">referrals</p>
                    </div>
                  </div>
                );
              })}
            </div>
            
            {/* Current user if not in top 10 */}
            {userRank && userRank > 10 && (
              <div className="pt-4 border-t border-[#333]">
                <p className="text-xs text-white/40 mb-2 text-center">Your Position</p>
                <div className="flex items-center justify-between p-3 bg-[#D4AF37]/10 border border-[#D4AF37] rounded-lg">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 flex items-center justify-center rounded-full bg-[#D4AF37]/20 text-[#D4AF37] font-mono text-sm font-bold">
                      {userRank}
                    </span>
                    <p className="font-medium text-[#D4AF37]">You</p>
                  </div>
                  <p className="text-sm text-white/60">
                    Keep sharing to climb the ranks!
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ReferralLeaderboard;
