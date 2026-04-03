import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Coins, Gift, TrendingUp, History, Sparkles, ChevronRight } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

// Points value constant (must match backend)
const POINT_VALUE = 0.05; // $0.05 per point

const LoyaltyPointsWidget = ({ compact = false, showRedeem = false, onRedemptionComplete }) => {
  const [points, setPoints] = useState(0);
  const [value, setValue] = useState(0);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showHistory, setShowHistory] = useState(false);
  const [redeemAmount, setRedeemAmount] = useState(0);
  const [redeeming, setRedeeming] = useState(false);

  useEffect(() => {
    fetchPoints();
  }, []);

  const fetchPoints = async () => {
    try {
      const token = localStorage.getItem('reroots_token');
      if (!token) {
        setLoading(false);
        return;
      }

      const res = await axios.get(`${API}/loyalty/points`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setPoints(res.data.points || 0);
      setValue(res.data.value || 0);
      setHistory(res.data.history || []);
    } catch (err) {
      console.error('Error fetching points:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRedeem = async () => {
    if (redeemAmount < 100) {
      toast.error('Minimum 100 points to redeem');
      return;
    }
    if (redeemAmount > points) {
      toast.error('Insufficient points');
      return;
    }

    setRedeeming(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.post(`${API}/loyalty/points/redeem`, 
        { points: redeemAmount },
        { headers: { Authorization: `Bearer ${token}` }}
      );

      toast.success(`Redeeming ${redeemAmount} points for $${res.data.discount_value} off!`);
      
      if (onRedemptionComplete) {
        onRedemptionComplete(res.data);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to redeem points');
    } finally {
      setRedeeming(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse">
        <div className="h-20 bg-gray-200 rounded-xl" />
      </div>
    );
  }

  // Compact version for header/sidebar
  if (compact) {
    return (
      <div 
        className="flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-amber-50 to-yellow-50 rounded-full cursor-pointer hover:shadow-md transition-shadow"
        onClick={() => setShowHistory(true)}
      >
        <Coins className="w-4 h-4 text-amber-600" />
        <span className="font-bold text-amber-700">{points.toLocaleString()}</span>
        <span className="text-xs text-amber-600">pts</span>
        <Badge variant="outline" className="text-xs border-amber-300 text-amber-700">
          ${value.toFixed(2)}
        </Badge>
      </div>
    );
  }

  // Full card version
  return (
    <>
      <Card className="bg-gradient-to-br from-amber-50 via-yellow-50 to-orange-50 border-amber-200 overflow-hidden">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-amber-500/20 rounded-xl">
                <Coins className="w-5 h-5 text-amber-600" />
              </div>
              <span className="font-display text-lg">Your Roots</span>
            </div>
            <Button 
              variant="ghost" 
              size="sm"
              onClick={() => setShowHistory(true)}
              className="text-amber-600 hover:text-amber-700"
            >
              <History className="w-4 h-4 mr-1" />
              History
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Roots Balance */}
          <div className="text-center py-4">
            <div className="flex items-baseline justify-center gap-1">
              <span className="text-5xl font-bold text-amber-600" style={{ fontFamily: '"JetBrains Mono", monospace' }}>
                {points.toLocaleString()}
              </span>
              <span className="text-xl text-amber-500">Roots</span>
            </div>
            <p className="text-amber-700 mt-1">
              Worth <span className="font-bold">${value.toFixed(2)}</span>
            </p>
          </div>

          {/* How it works */}
          <div className="bg-white/60 rounded-xl p-4 space-y-2">
            <p className="text-sm font-medium text-amber-800 flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              How to earn more Roots
            </p>
            <ul className="text-sm text-amber-700 space-y-1">
              <li className="flex items-center gap-2">
                <Gift className="w-3 h-3" />
                <span>250 Roots per product purchased</span>
              </li>
              <li className="flex items-center gap-2">
                <TrendingUp className="w-3 h-3" />
                <span>1 Root = $0.05 value</span>
              </li>
            </ul>
          </div>

          {/* Redeem Section */}
          {showRedeem && points >= 100 && (
            <div className="border-t border-amber-200 pt-4 space-y-3">
              <p className="text-sm font-medium text-amber-800">Redeem Roots</p>
              <div className="flex gap-2">
                <Input
                  type="number"
                  min={100}
                  max={points}
                  step={50}
                  value={redeemAmount}
                  onChange={(e) => setRedeemAmount(Math.min(points, Math.max(0, parseInt(e.target.value) || 0)))}
                  placeholder="Roots to redeem"
                  className="flex-1"
                />
                <Button 
                  onClick={handleRedeem}
                  disabled={redeeming || redeemAmount < 100}
                  className="bg-amber-500 hover:bg-amber-600 text-white"
                >
                  {redeeming ? 'Redeeming...' : `Get $${(redeemAmount * POINT_VALUE).toFixed(2)} Off`}
                </Button>
              </div>
              <p className="text-xs text-amber-600">Minimum 100 Roots to redeem</p>
            </div>
          )}

          {/* CTA for users with no points */}
          {points === 0 && (
            <div className="text-center py-2">
              <p className="text-sm text-amber-700 mb-2">Start earning Roots with your first purchase!</p>
              <Button variant="outline" className="border-amber-300 text-amber-700 hover:bg-amber-50" asChild>
                <a href="/shop">
                  Shop Now <ChevronRight className="w-4 h-4 ml-1" />
                </a>
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* History Dialog */}
      <Dialog open={showHistory} onOpenChange={setShowHistory}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <History className="w-5 h-5 text-amber-600" />
              Roots History
            </DialogTitle>
            <DialogDescription>
              Your recent points activity
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {history.length === 0 ? (
              <p className="text-center text-gray-500 py-8">No points activity yet</p>
            ) : (
              history.slice().reverse().map((item, idx) => (
                <div 
                  key={item.id || idx}
                  className={`flex items-center justify-between p-3 rounded-lg ${
                    item.type === 'earned' ? 'bg-green-50' : 'bg-red-50'
                  }`}
                >
                  <div>
                    <p className="font-medium text-sm">
                      {item.description}
                    </p>
                    <p className="text-xs text-gray-500">
                      {new Date(item.date).toLocaleDateString()}
                    </p>
                  </div>
                  <span className={`font-bold ${
                    item.type === 'earned' ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {item.type === 'earned' ? '+' : ''}{item.points} pts
                  </span>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default LoyaltyPointsWidget;
