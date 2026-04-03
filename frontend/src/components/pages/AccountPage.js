import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';

// UI Components
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Separator } from '../ui/separator';

// Icons
import { 
  Loader2, Package, Truck, MapPin, Clock, CheckCircle, XCircle, 
  Gift, Share2, Users, Copy, ExternalLink, AlertTriangle, Star,
  ChevronRight, RefreshCw, Send, Sparkles, ArrowRight, ArrowLeft,
  DollarSign, Mail, Phone, MessageSquare, Calendar, Leaf, CreditCard
} from 'lucide-react';

// Contexts
import { useAuth } from '../../contexts';

// Lazy load Transformation Calendar
const TransformationCalendar = React.lazy(() => import('../account/TransformationCalendar'));

// Dynamic API URL for custom domains
const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    if (!hostname.includes('preview.emergentagent.com') && !hostname.includes('emergent.host')) {
      return window.location.origin;
    }
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};

const API = getBackendUrl() + '/api';

const AccountPage = () => {
  const { user, loading: authLoading, authChecked } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [trackingInfo, setTrackingInfo] = useState(null);
  const [loadingTracking, setLoadingTracking] = useState(false);
  const [cancellingOrder, setCancellingOrder] = useState(null);
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [orderToCancel, setOrderToCancel] = useState(null);
  const [myOffers, setMyOffers] = useState([]);
  const [loadingOffers, setLoadingOffers] = useState(true);
  const [activeTab, setActiveTab] = useState("orders");
  const [referralInfo, setReferralInfo] = useState(null);
  const [partnerStatus, setPartnerStatus] = useState(null);
  const [loadingPartnerStatus, setLoadingPartnerStatus] = useState(true);
  const [calendarOrder, setCalendarOrder] = useState(null); // For transformation calendar
  
  // Gift Points state
  const [giftHistory, setGiftHistory] = useState({ sent: [], received: [], total_sent: 0, total_received: 0 });
  const [loadingGifts, setLoadingGifts] = useState(true);
  const [pointsBalance, setPointsBalance] = useState(0);
  const [giftRecipient, setGiftRecipient] = useState("");
  const [giftAmount, setGiftAmount] = useState("");
  const [giftMessage, setGiftMessage] = useState("");
  const [sendingGift, setSendingGift] = useState(false);
  const [buyAmount, setBuyAmount] = useState("");
  const [buyingPoints, setBuyingPoints] = useState(false);
  const [showPaymentForm, setShowPaymentForm] = useState(false);
  const [cardDetails, setCardDetails] = useState({
    cardNumber: "",
    expiryMonth: "",
    expiryYear: "",
    cvv: "",
    cardholderName: ""
  });
  
  // Gift with Shop Link state (enhanced gifting)
  const [giftWithLink, setGiftWithLink] = useState(true); // Default to new enhanced mode
  const [giftRecipientName, setGiftRecipientName] = useState("");
  const [giftRecipientPhone, setGiftRecipientPhone] = useState("");
  const [giftLinkResult, setGiftLinkResult] = useState(null);

  const loadOrders = useCallback(() => {
    axios.get(`${API}/orders`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` }
    })
      .then(res => setOrders(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const loadGiftHistory = useCallback(() => {
    setLoadingGifts(true);
    axios.get(`${API}/rewards/gift-history`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` }
    })
      .then(res => setGiftHistory(res.data))
      .catch(console.error)
      .finally(() => setLoadingGifts(false));
  }, []);

  const loadPointsBalance = useCallback(() => {
    axios.get(`${API}/rewards/profile`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` }
    })
      .then(res => setPointsBalance(res.data.points_balance || 0))
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (user) {
      loadOrders();
      loadGiftHistory();
      loadPointsBalance();
      // Load referral info
      axios.get(`${API}/referral/info`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` }
      }).then(res => setReferralInfo(res.data)).catch(() => {});
      
      // Load partner status
      axios.get(`${API}/partner/status`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` }
      }).then(res => setPartnerStatus(res.data)).catch(() => {}).finally(() => setLoadingPartnerStatus(false));
      
      // Load offers
      axios.get(`${API}/my-offers`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` }
      }).then(res => setMyOffers(res.data?.offers || res.data || [])).catch(() => {}).finally(() => setLoadingOffers(false));
      
      // Claim any pending gifts
      axios.post(`${API}/rewards/claim-pending-gifts`, {}, {
        headers: { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` }
      }).then(res => {
        if (res.data.claimed > 0) {
          toast.success(res.data.message);
          loadPointsBalance();
          loadGiftHistory();
        }
      }).catch(() => {});
    }
  }, [user, loadOrders, loadGiftHistory, loadPointsBalance]);

  const sendGift = async () => {
    // Use the new /api/account/gift-points endpoint (Task 3)
    if (!giftRecipient) {
      toast.error("Please enter recipient email");
      return;
    }
    
    const amount = parseInt(giftAmount);
    if (amount < 50) {
      toast.error("Minimum gift is 50 Roots");
      return;
    }
    
    if (amount > pointsBalance) {
      toast.error("Insufficient Roots balance");
      return;
    }
    
    setSendingGift(true);
    try {
      const res = await axios.post(`${API}/account/gift-points`, {
        recipient_email: giftRecipient,
        points: amount,
        message: giftMessage
      }, {
        headers: { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` }
      });
      
      // Build result for UI
      const result = {
        points_sent: res.data.points_gifted,
        points_value: res.data.gift_value,
        recipient_name: giftRecipient.split("@")[0],
        bonus_earned: res.data.bonus_earned,
        new_balance: res.data.new_sender_balance,
        recipient_is_new: res.data.recipient_is_new,
        notifications_sent: { email: true, whatsapp: true }
      };
      
      setGiftLinkResult(result);
      
      // Show success message with bonus if applicable
      if (res.data.bonus_earned > 0) {
        toast.success(`🎁 Gift sent! +${res.data.bonus_earned} bonus Roots for introducing a new member!`);
      } else {
        toast.success(`🎁 ${res.data.points_gifted} Roots sent to ${giftRecipient}!`);
      }
      
      // Update balance immediately
      setPointsBalance(res.data.new_sender_balance);
      loadGiftHistory();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to send gift");
    } finally {
      setSendingGift(false);
    }
  };
  
  const resetGiftForm = () => {
    setGiftRecipient("");
    setGiftRecipientName("");
    setGiftRecipientPhone("");
    setGiftAmount("");
    setGiftMessage("");
    setGiftLinkResult(null);
  };

  const initiateBuyPoints = (dollars) => {
    const amount = parseInt(dollars);
    if (!amount || amount < 1) {
      toast.error("Please enter a valid amount");
      return;
    }
    setBuyAmount(amount.toString());
    setShowPaymentForm(true);
  };

  const buyPoints = async () => {
    const amount = parseInt(buyAmount);
    if (!amount || amount < 1) {
      toast.error("Please enter a valid amount");
      return;
    }
    
    // Validate card details
    if (!cardDetails.cardNumber || !cardDetails.expiryMonth || !cardDetails.expiryYear || !cardDetails.cvv || !cardDetails.cardholderName) {
      toast.error("Please fill in all card details");
      return;
    }
    
    setBuyingPoints(true);
    try {
      const res = await axios.post(`${API}/rewards/buy-points`, {
        amount: amount,
        card_number: cardDetails.cardNumber,
        expiry_month: cardDetails.expiryMonth,
        expiry_year: cardDetails.expiryYear,
        cvv: cardDetails.cvv,
        cardholder_name: cardDetails.cardholderName
      }, {
        headers: { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` }
      });
      
      toast.success(res.data.message);
      setBuyAmount("");
      setShowPaymentForm(false);
      setCardDetails({ cardNumber: "", expiryMonth: "", expiryYear: "", cvv: "", cardholderName: "" });
      loadPointsBalance();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to purchase Roots");
    } finally {
      setBuyingPoints(false);
    }
  };

  const copyReferralLink = () => {
    if (referralInfo?.referral_code) {
      navigator.clipboard.writeText(`https://reroots.ca?ref=${referralInfo.referral_code}`);
      toast.success("Referral link copied!");
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'completed': case 'delivered': return 'bg-green-100 text-green-800';
      case 'shipped': case 'in_transit': return 'bg-blue-100 text-blue-800';
      case 'processing': case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'cancelled': case 'refunded': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const handleCancelOrder = async () => {
    if (!orderToCancel) return;
    setCancellingOrder(orderToCancel.id);
    try {
      await axios.post(`${API}/orders/${orderToCancel.id}/cancel`, 
        { reason: cancelReason },
        { headers: { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` }}
      );
      toast.success("Order cancelled successfully");
      loadOrders();
      setShowCancelDialog(false);
      setCancelReason("");
      setOrderToCancel(null);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to cancel order");
    } finally {
      setCancellingOrder(null);
    }
  };

  // Show loading while auth is being checked
  // Fallback to checking if authChecked is explicitly false (not just undefined)
  if (authLoading || authChecked === false) {
    return (
      <div className="min-h-screen pt-24 flex items-center justify-center bg-[#FDF9F9]">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen pt-24 flex items-center justify-center bg-gradient-to-b from-[#FDF9F9] to-[#FFF5F7]">
        <Card className="max-w-md w-full mx-4 shadow-lg border-0">
          <CardContent className="pt-8 pb-8 text-center">
            {/* Logo */}
            <div className="mb-6">
              <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">Welcome to ReRoots</h2>
              <p className="text-sm text-[#5A5A5A] mt-1">Your skincare journey awaits</p>
            </div>
            
            {/* Icon */}
            <div className="w-16 h-16 bg-gradient-to-r from-[#F8A5B8] to-pink-400 rounded-full flex items-center justify-center mx-auto mb-6">
              <Package className="h-8 w-8 text-white" />
            </div>
            
            <p className="text-[#5A5A5A] mb-6">Sign in to view your orders, track shipments, and access your transformation calendar.</p>
            
            <Link to="/login">
              <Button className="w-full bg-gradient-to-r from-[#2D2A2E] to-[#3d393d] hover:from-[#3d393d] hover:to-[#4d494d] text-white py-6 text-lg font-medium">
                Sign In to Your Account
              </Button>
            </Link>
            
            <p className="text-sm text-[#5A5A5A] mt-4">
              Don't have an account?{' '}
              <Link to="/login" className="text-[#F8A5B8] font-medium hover:underline">
                Create one
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 bg-[#FDF9F9]">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="font-display text-3xl font-bold text-[#2D2A2E]">My Account</h1>
          <p className="text-[#5A5A5A] mt-1">Welcome back, {user.first_name || user.email}</p>
        </div>

        {/* Roots Balance Banner - Task 8 */}
        <div className="mb-6 bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200 rounded-xl p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-emerald-500 rounded-full flex items-center justify-center">
                <Leaf className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-sm font-medium text-emerald-700">Your Roots Balance</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold text-emerald-800">{pointsBalance}</span>
                  <span className="text-lg text-emerald-600">Roots</span>
                  <span className="text-sm text-emerald-600">(${(pointsBalance * 0.05).toFixed(2)} value)</span>
                </div>
                {pointsBalance < 600 && (
                  <p className="text-xs text-emerald-600 mt-1">
                    {600 - pointsBalance} Roots away from 30% off!
                  </p>
                )}
                {pointsBalance >= 600 && (
                  <p className="text-xs text-emerald-700 font-medium mt-1">
                    🎉 You have enough for 30% off!
                  </p>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <Link to="/checkout">
                <Button variant="outline" className="border-emerald-300 text-emerald-700 hover:bg-emerald-100">
                  Redeem at Checkout
                </Button>
              </Link>
              <Button 
                onClick={() => setActiveTab('gift-points')} 
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                Gift Your Roots
              </Button>
            </div>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6 bg-white border">
            <TabsTrigger value="orders" className="data-[state=active]:bg-[#F8A5B8]/10">
              <Package className="h-4 w-4 mr-2" />
              Orders
            </TabsTrigger>
            <TabsTrigger value="gift-points" className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-amber-100 data-[state=active]:to-yellow-100">
              <Sparkles className="h-4 w-4 mr-2" />
              Gift Roots
            </TabsTrigger>
            <TabsTrigger value="referrals" className="data-[state=active]:bg-[#F8A5B8]/10">
              <Share2 className="h-4 w-4 mr-2" />
              Referrals
            </TabsTrigger>
            <TabsTrigger value="offers" className="data-[state=active]:bg-[#F8A5B8]/10">
              <Gift className="h-4 w-4 mr-2" />
              My Offers
            </TabsTrigger>
            <TabsTrigger value="transformation" className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-purple-100 data-[state=active]:to-pink-100">
              <Calendar className="h-4 w-4 mr-2" />
              12-Week Calendar
            </TabsTrigger>
          </TabsList>

          {/* Gift Roots Tab */}
          <TabsContent value="gift-points">
            {/* Current Roots Balance - Prominent Display */}
            <Card className="mb-6 bg-gradient-to-r from-amber-100 via-yellow-100 to-amber-100 border-amber-300 shadow-lg">
              <CardContent className="py-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-amber-700 font-medium">Your Roots Balance</p>
                    <div className="flex items-baseline gap-2">
                      <p className="text-4xl font-bold text-amber-800">{pointsBalance}</p>
                      <span className="text-xl text-amber-600">Roots</span>
                    </div>
                    <p className="text-sm text-amber-600 mt-1">
                      Worth ${(pointsBalance * 0.05).toFixed(2)} in discounts
                    </p>
                  </div>
                  <div className="text-6xl opacity-50">
                    <Sparkles className="h-16 w-16 text-amber-400" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-6 md:grid-cols-2">
              {/* Buy Roots Card */}
              <Card className="bg-gradient-to-br from-green-50 to-emerald-50 border-green-200">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-green-800">
                    <DollarSign className="h-5 w-5" />
                    Buy Roots
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-3 bg-white rounded-lg border border-green-200 text-center">
                    <p className="text-lg font-bold text-green-700">$1 = 20 Roots</p>
                    <p className="text-xs text-gray-500">$30 = 600 Roots (30% discount)</p>
                  </div>
                  
                  {!showPaymentForm ? (
                    <>
                      {/* Quick buy buttons */}
                      <div className="grid grid-cols-4 gap-2">
                        {[5, 10, 20, 30].map(amt => (
                          <Button
                            key={amt}
                            variant="outline"
                            size="sm"
                            onClick={() => initiateBuyPoints(amt)}
                            disabled={buyingPoints}
                            className="border-green-300 hover:bg-green-100"
                          >
                            ${amt}
                          </Button>
                        ))}
                      </div>
                      
                      <div className="flex gap-2">
                        <Input
                          placeholder="Custom amount ($)"
                          value={buyAmount}
                          onChange={(e) => setBuyAmount(e.target.value.replace(/\D/g, ''))}
                          type="text"
                          className="border-green-200 focus:border-green-400"
                        />
                        <Button 
                          onClick={() => initiateBuyPoints(buyAmount)}
                          disabled={buyingPoints || !buyAmount}
                          className="bg-green-600 hover:bg-green-700 text-white"
                        >
                          Buy
                        </Button>
                      </div>
                      
                      {buyAmount && (
                        <p className="text-sm text-center text-green-700">
                          ${buyAmount} = <span className="font-bold">{parseInt(buyAmount || 0) * 20} Roots</span>
                        </p>
                      )}
                    </>
                  ) : (
                    /* Payment Form */
                    <div className="space-y-3">
                      <div className="p-3 bg-green-100 rounded-lg text-center">
                        <p className="text-sm text-green-800">Purchasing <span className="font-bold">{parseInt(buyAmount || 0) * 20} Roots</span> for <span className="font-bold">${buyAmount}</span></p>
                      </div>
                      
                      <Input
                        placeholder="Cardholder Name"
                        value={cardDetails.cardholderName}
                        onChange={(e) => setCardDetails({...cardDetails, cardholderName: e.target.value})}
                        className="border-green-200"
                      />
                      <Input
                        placeholder="Card Number"
                        value={cardDetails.cardNumber}
                        onChange={(e) => setCardDetails({...cardDetails, cardNumber: e.target.value.replace(/\D/g, '').slice(0, 16)})}
                        className="border-green-200"
                      />
                      <div className="grid grid-cols-3 gap-2">
                        <Input
                          placeholder="MM"
                          value={cardDetails.expiryMonth}
                          onChange={(e) => setCardDetails({...cardDetails, expiryMonth: e.target.value.replace(/\D/g, '').slice(0, 2)})}
                          className="border-green-200"
                        />
                        <Input
                          placeholder="YY"
                          value={cardDetails.expiryYear}
                          onChange={(e) => setCardDetails({...cardDetails, expiryYear: e.target.value.replace(/\D/g, '').slice(0, 2)})}
                          className="border-green-200"
                        />
                        <Input
                          placeholder="CVV"
                          value={cardDetails.cvv}
                          onChange={(e) => setCardDetails({...cardDetails, cvv: e.target.value.replace(/\D/g, '').slice(0, 4)})}
                          className="border-green-200"
                          type="password"
                        />
                      </div>
                      
                      <div className="flex gap-2">
                        <Button 
                          variant="outline"
                          onClick={() => {
                            setShowPaymentForm(false);
                            setCardDetails({ cardNumber: "", expiryMonth: "", expiryYear: "", cvv: "", cardholderName: "" });
                          }}
                          className="flex-1"
                        >
                          Cancel
                        </Button>
                        <Button 
                          onClick={buyPoints}
                          disabled={buyingPoints}
                          className="flex-1 bg-green-600 hover:bg-green-700 text-white"
                        >
                          {buyingPoints ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                          Pay ${buyAmount}
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Send Gift Card - Gift Your Roots */}
              <Card className="bg-gradient-to-br from-amber-50 to-yellow-50 border-amber-200">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-amber-800">
                    <Send className="h-5 w-5" />
                    Gift Your Roots
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Balance Display */}
                  <div className="p-3 bg-white rounded-lg border border-amber-200">
                    <p className="text-sm text-gray-600">Your Roots Balance</p>
                    <p className="text-2xl font-bold text-amber-700">{pointsBalance} Roots</p>
                    <p className="text-xs text-gray-500">${(pointsBalance * 0.05).toFixed(2)} value</p>
                  </div>
                  
                  {/* Gift Result Display */}
                  {giftLinkResult ? (
                    <div className="space-y-4">
                      <div className="p-4 bg-green-50 rounded-lg border border-green-200 text-center">
                        <div className="text-4xl mb-2">🎁</div>
                        <h3 className="font-bold text-green-800">Gift Sent Successfully!</h3>
                        <p className="text-sm text-green-700 mt-1">
                          {giftLinkResult.points_sent} Roots (${giftLinkResult.points_value?.toFixed(2)}) sent to {giftLinkResult.recipient_name || 'your friend'}
                        </p>
                      </div>
                      
                      {/* Bonus message for new customer referral */}
                      {giftLinkResult.bonus_earned > 0 && (
                        <div className="p-3 bg-amber-50 rounded-lg border border-amber-300 text-center">
                          <p className="text-amber-800 font-medium flex items-center justify-center gap-2">
                            <Sparkles className="h-4 w-4" />
                            Bonus: You earned {giftLinkResult.bonus_earned} Roots for introducing a new ReRoots member!
                          </p>
                        </div>
                      )}
                      
                      {/* New balance display */}
                      <div className="p-3 bg-white rounded-lg border border-green-200 text-center">
                        <p className="text-sm text-gray-600">Your New Balance</p>
                        <p className="text-2xl font-bold text-green-700">{giftLinkResult.new_balance} Roots</p>
                        <p className="text-xs text-gray-500">${(giftLinkResult.new_balance * 0.05).toFixed(2)} value</p>
                      </div>
                      
                      <div className="space-y-2 text-sm">
                        <p className="font-medium">Notifications sent via:</p>
                        <div className="flex gap-2 flex-wrap">
                          {giftLinkResult.notifications_sent?.email && (
                            <Badge className="bg-blue-100 text-blue-800">
                              <Mail className="h-3 w-3 mr-1" /> Email
                            </Badge>
                          )}
                          {giftLinkResult.notifications_sent?.sms && (
                            <Badge className="bg-green-100 text-green-800">
                              <Phone className="h-3 w-3 mr-1" /> SMS
                            </Badge>
                          )}
                          {giftLinkResult.notifications_sent?.whatsapp && (
                            <Badge className="bg-emerald-100 text-emerald-800">
                              <MessageSquare className="h-3 w-3 mr-1" /> WhatsApp
                            </Badge>
                          )}
                        </div>
                      </div>
                      
                      <Button 
                        onClick={resetGiftForm}
                        variant="outline"
                        className="w-full border-amber-300 hover:bg-amber-100"
                      >
                        Send Another Gift
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {/* Recipient Email */}
                      <div>
                        <label className="text-sm font-medium text-amber-800 mb-1 block">Recipient's Email</label>
                        <Input
                          placeholder="friend@email.com"
                          value={giftRecipient}
                          onChange={(e) => setGiftRecipient(e.target.value)}
                          type="email"
                          className="border-amber-200 focus:border-amber-400"
                        />
                        <p className="text-xs text-amber-600 mt-1">They'll receive an email with their Roots gift!</p>
                      </div>
                      
                      {/* Points Amount - Quick Select */}
                      <div className="space-y-2">
                        <p className="text-sm font-medium text-amber-800">Select Roots to gift:</p>
                        
                        {/* Quick select buttons based on balance */}
                        {pointsBalance >= 50 && (
                          <div className="grid grid-cols-4 gap-2">
                            {[100, 200, 500, pointsBalance].filter((p, i, arr) => 
                              p <= pointsBalance && (i < 3 || p === pointsBalance)
                            ).slice(0, 4).map(pts => (
                              <Button
                                key={pts}
                                variant={giftAmount === String(pts) ? "default" : "outline"}
                                size="sm"
                                onClick={() => setGiftAmount(String(pts))}
                                className={giftAmount === String(pts) 
                                  ? "bg-amber-500 hover:bg-amber-600 text-white" 
                                  : "border-amber-300 hover:bg-amber-100"
                                }
                              >
                                {pts === pointsBalance ? 'All' : pts}
                              </Button>
                            ))}
                          </div>
                        )}
                        
                        <Input
                          placeholder={`Roots to gift (max ${pointsBalance})`}
                          value={giftAmount}
                          onChange={(e) => {
                            const val = e.target.value.replace(/\D/g, '');
                            if (!val || parseInt(val) <= pointsBalance) {
                              setGiftAmount(val);
                            }
                          }}
                          type="text"
                          className="border-amber-200 focus:border-amber-400"
                        />
                        {giftAmount && parseInt(giftAmount) >= 50 && (
                          <p className="text-xs text-amber-700">
                            = ${(parseInt(giftAmount) * 0.05).toFixed(2)} value | 
                            <span className="ml-1">Remaining: {pointsBalance - parseInt(giftAmount || 0)} Roots</span>
                          </p>
                        )}
                        {giftAmount && parseInt(giftAmount) > pointsBalance && (
                          <p className="text-xs text-red-600">
                            Insufficient balance! You have {pointsBalance} pts
                          </p>
                        )}
                      </div>
                      
                      {/* Personal Message */}
                      <Input
                        placeholder="Add a personal message (optional)"
                        value={giftMessage}
                        onChange={(e) => setGiftMessage(e.target.value)}
                        className="border-amber-200 focus:border-amber-400"
                      />
                      
                      {/* Send Button */}
                      <Button 
                        onClick={sendGift} 
                        disabled={sendingGift || !giftRecipient || !giftAmount || parseInt(giftAmount) < 50 || parseInt(giftAmount) > pointsBalance}
                        className="w-full bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600 text-white"
                      >
                        {sendingGift ? (
                          <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        ) : (
                          <Send className="h-4 w-4 mr-2" />
                        )}
                        Send Gift with Shop Link
                      </Button>
                    </div>
                  )}
                  
                  <div className="p-3 bg-amber-100/50 rounded-lg">
                    <p className="text-xs text-amber-800">
                      <span className="font-semibold">🛍️ Shop Link Feature:</span> Recipients get a special link to claim their points. 
                      When they click it, they can sign up (or log in) and immediately use their Roots to shop!
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* Gift Stats Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-amber-500" />
                    Your Gift Activity
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div className="p-4 bg-green-50 rounded-lg text-center">
                      <ArrowRight className="h-5 w-5 mx-auto text-green-600 mb-1" />
                      <p className="text-2xl font-bold text-green-700">{giftHistory.total_sent}</p>
                      <p className="text-xs text-green-600">Points Sent</p>
                    </div>
                    <div className="p-4 bg-blue-50 rounded-lg text-center">
                      <ArrowLeft className="h-5 w-5 mx-auto text-blue-600 mb-1" />
                      <p className="text-2xl font-bold text-blue-700">{giftHistory.total_received}</p>
                      <p className="text-xs text-blue-600">Points Received</p>
                    </div>
                  </div>
                  
                  {loadingGifts ? (
                    <div className="flex justify-center py-4">
                      <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* Sent Gifts */}
                      {giftHistory.sent.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium text-gray-600 mb-2 flex items-center gap-1">
                            <ArrowRight className="h-4 w-4" /> Sent
                          </h4>
                          <div className="space-y-2 max-h-32 overflow-y-auto">
                            {giftHistory.sent.slice(0, 5).map((gift, idx) => (
                              <div key={idx} className="flex justify-between items-center p-2 bg-gray-50 rounded text-sm">
                                <span className="text-gray-600 truncate max-w-[150px]">{gift.recipient_email}</span>
                                <Badge variant="outline" className="text-green-600">-{gift.points} pts</Badge>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {/* Received Gifts */}
                      {giftHistory.received.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium text-gray-600 mb-2 flex items-center gap-1">
                            <ArrowLeft className="h-4 w-4" /> Received
                          </h4>
                          <div className="space-y-2 max-h-32 overflow-y-auto">
                            {giftHistory.received.slice(0, 5).map((gift, idx) => (
                              <div key={idx} className="flex justify-between items-center p-2 bg-gray-50 rounded text-sm">
                                <span className="text-gray-600 truncate max-w-[150px]">{gift.sender_name || gift.sender_email}</span>
                                <Badge variant="outline" className="text-blue-600">+{gift.points} pts</Badge>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {giftHistory.sent.length === 0 && giftHistory.received.length === 0 && (
                        <p className="text-center text-gray-500 text-sm py-4">
                          No gift activity yet. Start by sending Roots to a friend!
                        </p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Orders Tab */}
          <TabsContent value="orders">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Order History</CardTitle>
                <Button variant="outline" size="sm" onClick={loadOrders}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Refresh
                </Button>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="flex justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
                  </div>
                ) : orders.length === 0 ? (
                  <div className="text-center py-12">
                    <Package className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-[#5A5A5A]">No orders yet</p>
                    <Link to="/shop" className="mt-4 inline-block">
                      <Button>Start Shopping</Button>
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {orders.map((order) => (
                      <div key={order.id} className="border rounded-lg p-4 hover:shadow-md transition-shadow">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <p className="font-medium text-[#2D2A2E]">
                              Order #{order.order_number || order.id?.slice(0, 8)}
                            </p>
                            <p className="text-sm text-[#5A5A5A]">
                              {new Date(order.created_at).toLocaleDateString()}
                            </p>
                          </div>
                          <Badge className={getStatusColor(order.status)}>
                            {order.status || 'Processing'}
                          </Badge>
                        </div>
                        
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            {order.items?.slice(0, 3).map((item, idx) => (
                              <img 
                                key={idx}
                                src={item.product_image || item.product?.images?.[0] || item.image || '/placeholder.jpg'}
                                alt={item.product_name || item.product?.name || 'Product'}
                                className="w-12 h-12 object-cover rounded"
                              />
                            ))}
                            {order.items?.length > 3 && (
                              <span className="text-sm text-[#5A5A5A]">+{order.items.length - 3} more</span>
                            )}
                          </div>
                          <div className="text-right">
                            <p className="font-bold text-[#2D2A2E]">${order.total?.toFixed(2)}</p>
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={() => setSelectedOrder(order)}
                            >
                              View Details <ChevronRight className="h-4 w-4 ml-1" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Referrals Tab */}
          <TabsContent value="referrals">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-[#F8A5B8]" />
                  Referral Program
                </CardTitle>
              </CardHeader>
              <CardContent>
                {referralInfo ? (
                  <div className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="bg-gradient-to-br from-[#F8A5B8]/10 to-[#F8A5B8]/5 rounded-lg p-4 text-center">
                        <p className="text-3xl font-bold text-[#2D2A2E]">{referralInfo.total_referrals || 0}</p>
                        <p className="text-sm text-[#5A5A5A]">Total Referrals</p>
                      </div>
                      <div className="bg-gradient-to-br from-green-100 to-green-50 rounded-lg p-4 text-center">
                        <p className="text-3xl font-bold text-green-700">{referralInfo.successful_referrals || 0}</p>
                        <p className="text-sm text-[#5A5A5A]">Successful</p>
                      </div>
                      <div className="bg-gradient-to-br from-[#C9A86C]/10 to-[#C9A86C]/5 rounded-lg p-4 text-center">
                        <p className="text-3xl font-bold text-[#C9A86C]">${referralInfo.total_earned?.toFixed(2) || '0.00'}</p>
                        <p className="text-sm text-[#5A5A5A]">Earned</p>
                      </div>
                    </div>

                    <Separator />

                    <div>
                      <p className="font-medium text-[#2D2A2E] mb-2">Your Referral Link</p>
                      <div className="flex gap-2">
                        <Input 
                          value={`https://reroots.ca?ref=${referralInfo.referral_code}`}
                          readOnly
                          className="bg-gray-50"
                        />
                        <Button onClick={copyReferralLink}>
                          <Copy className="h-4 w-4 mr-2" />
                          Copy
                        </Button>
                      </div>
                      <p className="text-sm text-[#5A5A5A] mt-2">
                        Share this link and earn rewards when friends make their first purchase!
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8] mx-auto mb-4" />
                    <p className="text-[#5A5A5A]">Loading referral info...</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Offers Tab */}
          <TabsContent value="offers">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Gift className="h-5 w-5 text-[#F8A5B8]" />
                  My Offers & Rewards
                </CardTitle>
              </CardHeader>
              <CardContent>
                {loadingOffers ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
                  </div>
                ) : myOffers.length === 0 ? (
                  <div className="text-center py-8">
                    <Gift className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-[#5A5A5A]">No offers available</p>
                    <p className="text-sm text-[#5A5A5A] mt-1">Keep shopping to unlock rewards!</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {myOffers.map((offer, idx) => (
                      <div key={idx} className="border rounded-lg p-4 bg-gradient-to-r from-[#F8A5B8]/5 to-white">
                        <div className="flex items-start justify-between">
                          <div>
                            <p className="font-medium text-[#2D2A2E]">{offer.title}</p>
                            <p className="text-sm text-[#5A5A5A] mt-1">{offer.description}</p>
                          </div>
                          <Badge>{offer.discount}% OFF</Badge>
                        </div>
                        {offer.code && (
                          <div className="mt-3 flex items-center gap-2">
                            <code className="bg-gray-100 px-3 py-1 rounded text-sm">{offer.code}</code>
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={() => {
                                navigator.clipboard.writeText(offer.code);
                                toast.success("Code copied!");
                              }}
                            >
                              <Copy className="h-4 w-4" />
                            </Button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* 12-Week Transformation Calendar Tab */}
          <TabsContent value="transformation">
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Calendar className="h-5 w-5 text-purple-600" />
                  Your 12-Week Transformation Journey
                </CardTitle>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
                  </div>
                ) : orders.length === 0 ? (
                  <div className="text-center py-8">
                    <Calendar className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-[#5A5A5A]">No transformation journey yet</p>
                    <p className="text-sm text-[#5A5A5A] mt-1">
                      Purchase a clinical combo to unlock your 12-week transformation calendar!
                    </p>
                    <Button className="mt-4" onClick={() => window.location.href = '/sets'}>
                      <Sparkles className="h-4 w-4 mr-2" />
                      Explore Clinical Protocols
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <p className="text-sm text-gray-600 mb-4">
                      Select an order to view your personalized transformation calendar:
                    </p>
                    <div className="grid gap-3">
                      {orders.slice(0, 5).map((order) => (
                        <div 
                          key={order.id}
                          className={`p-4 border rounded-lg cursor-pointer transition-all ${
                            calendarOrder?.id === order.id 
                              ? 'border-purple-500 bg-purple-50 ring-2 ring-purple-200' 
                              : 'hover:border-purple-300 hover:bg-purple-50/50'
                          }`}
                          onClick={() => setCalendarOrder(order)}
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="font-medium">Order #{order.order_number || order.id?.slice(0, 8)}</p>
                              <p className="text-sm text-gray-500">
                                {new Date(order.created_at).toLocaleDateString()} • {order.items?.length || 0} items
                              </p>
                            </div>
                            <ChevronRight className={`h-5 w-5 ${calendarOrder?.id === order.id ? 'text-purple-600' : 'text-gray-400'}`} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Show Calendar for Selected Order */}
            {calendarOrder && (
              <React.Suspense fallback={
                <Card>
                  <CardContent className="p-8 text-center">
                    <Loader2 className="h-8 w-8 animate-spin text-purple-600 mx-auto mb-2" />
                    <p className="text-gray-500">Loading your transformation calendar...</p>
                  </CardContent>
                </Card>
              }>
                <TransformationCalendar 
                  orderId={calendarOrder.id}
                  comboName={calendarOrder.items?.[0]?.product_name || "Your Clinical Protocol"}
                  customerName={user?.name || user?.email?.split('@')[0]}
                  orderDate={calendarOrder.created_at}
                />
              </React.Suspense>
            )}
          </TabsContent>
        </Tabs>

        {/* Order Details Dialog */}
        <Dialog open={!!selectedOrder} onOpenChange={() => setSelectedOrder(null)}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Order #{selectedOrder?.order_number || selectedOrder?.id?.slice(0, 8)}</DialogTitle>
            </DialogHeader>
            {selectedOrder && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Badge className={getStatusColor(selectedOrder.status)}>
                    {selectedOrder.status || 'Processing'}
                  </Badge>
                  <p className="text-sm text-[#5A5A5A]">
                    {new Date(selectedOrder.created_at).toLocaleDateString()}
                  </p>
                </div>

                <Separator />

                <div>
                  <h4 className="font-medium mb-2">Items</h4>
                  {selectedOrder.items?.map((item, idx) => (
                    <div key={idx} className="flex items-center gap-4 py-2">
                      <img 
                        src={item.product_image || item.product?.images?.[0] || item.image || '/placeholder.jpg'}
                        alt={item.product_name || item.product?.name || 'Product'}
                        className="w-16 h-16 object-cover rounded"
                      />
                      <div className="flex-1">
                        <p className="font-medium">{item.product_name || item.product?.name || 'Product'}</p>
                        <p className="text-sm text-[#5A5A5A]">Qty: {item.quantity}</p>
                      </div>
                      <p className="font-medium">${((item.price || item.product?.price || 0) * item.quantity).toFixed(2)}</p>
                    </div>
                  ))}
                </div>

                <Separator />

                <div className="flex justify-between items-center">
                  <span className="font-bold">Total</span>
                  <span className="font-bold text-lg">${selectedOrder.total?.toFixed(2)}</span>
                </div>

                {selectedOrder.shipping_address && (
                  <>
                    <Separator />
                    <div>
                      <h4 className="font-medium mb-2 flex items-center gap-2">
                        <MapPin className="h-4 w-4" />
                        Shipping Address
                      </h4>
                      <p className="text-sm text-[#5A5A5A]">
                        {selectedOrder.shipping_address.first_name} {selectedOrder.shipping_address.last_name}<br />
                        {selectedOrder.shipping_address.address_line1}<br />
                        {selectedOrder.shipping_address.city}, {selectedOrder.shipping_address.province} {selectedOrder.shipping_address.postal_code}
                      </p>
                    </div>
                  </>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default AccountPage;
