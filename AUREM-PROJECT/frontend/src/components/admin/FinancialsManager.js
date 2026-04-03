import React, { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import { AuthContext } from "@/contexts";
import { useContext } from "react";
import {
  Plus,
  Trash2,
  Check,
  Download,
  DollarSign,
  Users,
  Send,
  Loader2,
  Mail,
  Receipt,
  X
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Get backend URL from environment
const getBackendUrl = () => {
  return process.env.REACT_APP_BACKEND_URL || window.location.origin;
};

const API = `${getBackendUrl()}/api`;

// Auth hook
const useAuth = () => useContext(AuthContext);

const FinancialsManager = () => {
  const { user } = useAuth();
  const [financials, setFinancials] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("month");
  const [orders, setOrders] = useState([]);
  const [editingShippingCost, setEditingShippingCost] = useState(null);
  const [shippingCostValue, setShippingCostValue] = useState("");
  const [showSendModal, setShowSendModal] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState("");
  const [accountantEmail, setAccountantEmail] = useState("");
  const [reportMessage, setReportMessage] = useState("");
  const [sending, setSending] = useState(false);
  
  const headers = useMemo(() => ({
    Authorization: `Bearer ${localStorage.getItem("reroots_token")}`
  }), []);
  
  const loadFinancials = useCallback(async () => {
    setLoading(true);
    try {
      const [finRes, ordersRes] = await Promise.all([
        axios.get(`${API}/admin/financials?period=${period}`, { headers }),
        axios.get(`${API}/admin/financials/orders`, { headers })
      ]);
      setFinancials(finRes.data);
      setOrders(ordersRes.data.orders || []);
    } catch (error) {
      console.error("Failed to load financials:", error);
      toast.error("Failed to load financial data");
    }
    setLoading(false);
  }, [period, headers]);
  
  useEffect(() => {
    loadFinancials();
  }, [loadFinancials]);
  
  const exportReport = () => {
    window.open(`${API}/admin/financials/export?period=${period}&format=csv`, '_blank');
    toast.success("Downloading P&L report...");
  };
  
  const sendToAccountant = async () => {
    if (!accountantEmail) {
      toast.error("Please enter accountant's email");
      return;
    }
    setSending(true);
    try {
      await axios.post(`${API}/admin/financials/send-report`, {
        email: accountantEmail,
        period: period,
        message: reportMessage
      }, { headers });
      toast.success(`Report sent to ${accountantEmail}`);
      setShowSendModal(false);
      setAccountantEmail("");
      setReportMessage("");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send report");
    }
    setSending(false);
  };
  
  const createAccountantRole = async () => {
    try {
      const res = await axios.post(`${API}/admin/roles/accountant`, {}, { headers });
      toast.success(res.data.message);
    } catch (error) {
      toast.error("Failed to create accountant role");
    }
  };
  
  // Expense state
  const [expenses, setExpenses] = useState([]);
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [expenseCategories] = useState([
    "Inventory/Products", "Shipping/Courier", "Marketing/Advertising", 
    "Software/Subscriptions", "Office Supplies", "Equipment",
    "Professional Services", "Rent/Utilities", "Travel", "Packaging",
    "Bank Fees", "Insurance", "Taxes/Licenses", "Other"
  ]);
  const [expenseForm, setExpenseForm] = useState({
    category: "Other",
    description: "",
    amount: "",
    date: new Date().toISOString().split('T')[0],
    vendor: "",
    receipt_url: null,
    notes: ""
  });
  const [uploadingReceipt, setUploadingReceipt] = useState(false);
  
  const loadExpenses = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/admin/expenses?period=${period}`, { headers });
      setExpenses(res.data.expenses || []);
    } catch (error) {
      console.error("Failed to load expenses:", error);
    }
  }, [period, headers]);
  
  useEffect(() => {
    loadExpenses();
  }, [loadExpenses]);
  
  const handleReceiptUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    setUploadingReceipt(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await axios.post(`${API}/admin/expenses/upload-receipt`, formData, {
        headers: { ...headers, "Content-Type": "multipart/form-data" }
      });
      setExpenseForm({ ...expenseForm, receipt_url: res.data.url });
      toast.success("Receipt uploaded!");
    } catch (error) {
      toast.error("Failed to upload receipt");
    }
    setUploadingReceipt(false);
  };
  
  const submitExpense = async () => {
    if (!expenseForm.description || !expenseForm.amount) {
      toast.error("Please fill in description and amount");
      return;
    }
    try {
      await axios.post(`${API}/admin/expenses`, {
        ...expenseForm,
        amount: parseFloat(expenseForm.amount) || 0
      }, { headers });
      toast.success("Expense added!");
      setShowExpenseForm(false);
      setExpenseForm({
        category: "Other",
        description: "",
        amount: "",
        date: new Date().toISOString().split('T')[0],
        vendor: "",
        receipt_url: null,
        notes: ""
      });
      loadExpenses();
      loadFinancials();
    } catch (error) {
      toast.error("Failed to add expense");
    }
  };
  
  const deleteExpense = async (id) => {
    if (!window.confirm("Delete this expense?")) return;
    try {
      await axios.delete(`${API}/admin/expenses/${id}`, { headers });
      toast.success("Expense deleted");
      loadExpenses();
      loadFinancials();
    } catch (error) {
      toast.error("Failed to delete expense");
    }
  };
  
  const updateShippingCost = async (orderId) => {
    try {
      await axios.put(`${API}/admin/orders/${orderId}/shipping-cost`, {
        shipping_cost_paid: parseFloat(shippingCostValue) || 0
      }, { headers });
      toast.success("Shipping cost updated!");
      setEditingShippingCost(null);
      setShippingCostValue("");
      loadFinancials();
    } catch (error) {
      toast.error("Failed to update shipping cost");
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">💰 Financial Overview</h2>
        <div className="flex flex-wrap gap-2">
          {["today", "week", "month", "year", "all"].map(p => (
            <Button 
              key={p}
              variant={period === p ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriod(p)}
              className={period === p ? "bg-emerald-600 hover:bg-emerald-700" : ""}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </Button>
          ))}
        </div>
      </div>
      
      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3">
        <Button onClick={exportReport} variant="outline" className="border-emerald-500 text-emerald-600 hover:bg-emerald-50">
          <Download className="h-4 w-4 mr-2" />
          Export CSV
        </Button>
        <Button onClick={() => window.print()} variant="outline" className="border-gray-500 text-gray-600 hover:bg-gray-50">
          <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" /></svg>
          Print Report
        </Button>
        <Button onClick={() => setShowSendModal(true)} className="bg-blue-600 hover:bg-blue-700">
          <Send className="h-4 w-4 mr-2" />
          Send to Accountant
        </Button>
        <Button onClick={() => setShowPaymentModal(true)} variant="outline" className="border-green-500 text-green-600 hover:bg-green-50">
          <DollarSign className="h-4 w-4 mr-2" />
          Pay Tax / Transfer
        </Button>
        <Button onClick={createAccountantRole} variant="outline" className="border-purple-500 text-purple-600 hover:bg-purple-50">
          <Users className="h-4 w-4 mr-2" />
          Create Accountant Role
        </Button>
      </div>
      
      {/* Payment/Transfer Modal */}
      {showPaymentModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 print:hidden">
          <Card className="w-full max-w-lg mx-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-5 w-5 text-green-600" />
                Payment & Transfer Options
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-amber-50 p-4 rounded-lg">
                <p className="font-semibold text-amber-800">Tax Liability for {period.toUpperCase()}</p>
                <p className="text-3xl font-bold text-amber-700">${financials?.tax_liability?.toFixed(2) || "0.00"}</p>
                <p className="text-sm text-amber-600">Amount to pay to CRA (Canada Revenue Agency)</p>
              </div>
              
              <div className="space-y-3">
                <p className="font-medium text-gray-700">Select Payment Method:</p>
                
                {/* Auto Deposit Option */}
                <div 
                  className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${paymentMethod === 'auto_deposit' ? 'border-green-500 bg-green-50' : 'border-gray-200 hover:border-green-300'}`}
                  onClick={() => setPaymentMethod('auto_deposit')}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'auto_deposit' ? 'border-green-500' : 'border-gray-300'}`}>
                      {paymentMethod === 'auto_deposit' && <div className="w-3 h-3 rounded-full bg-green-500"></div>}
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold text-gray-800">🏦 Auto Deposit / Direct Transfer</p>
                      <p className="text-sm text-gray-500">Automatic bank transfer (EFT/ACH)</p>
                    </div>
                  </div>
                </div>
                
                {/* Bank Cheque Option */}
                <div 
                  className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${paymentMethod === 'cheque' ? 'border-green-500 bg-green-50' : 'border-gray-200 hover:border-green-300'}`}
                  onClick={() => setPaymentMethod('cheque')}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'cheque' ? 'border-green-500' : 'border-gray-300'}`}>
                      {paymentMethod === 'cheque' && <div className="w-3 h-3 rounded-full bg-green-500"></div>}
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold text-gray-800">📝 Bank Cheque</p>
                      <p className="text-sm text-gray-500">Mail a cheque to CRA</p>
                    </div>
                  </div>
                </div>
                
                {/* Online Banking Option */}
                <div 
                  className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${paymentMethod === 'online' ? 'border-green-500 bg-green-50' : 'border-gray-200 hover:border-green-300'}`}
                  onClick={() => setPaymentMethod('online')}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'online' ? 'border-green-500' : 'border-gray-300'}`}>
                      {paymentMethod === 'online' && <div className="w-3 h-3 rounded-full bg-green-500"></div>}
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold text-gray-800">💻 Online Banking / CRA My Payment</p>
                      <p className="text-sm text-gray-500">Pay through your bank's bill payment</p>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="flex gap-2 justify-end pt-4">
                <Button variant="outline" onClick={() => setShowPaymentModal(false)}>Close</Button>
                <Button onClick={() => { toast.success("Payment method saved!"); setShowPaymentModal(false); }} className="bg-green-600 hover:bg-green-700">
                  Save Payment Info
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
      
      {/* Send to Accountant Modal */}
      {showSendModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 print:hidden">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5 text-blue-600" />
                Send P&L Report to Accountant
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Accountant's Email *</Label>
                <Input
                  type="email"
                  value={accountantEmail}
                  onChange={(e) => setAccountantEmail(e.target.value)}
                  placeholder="accountant@example.com"
                />
              </div>
              <div>
                <Label>Note (Optional)</Label>
                <textarea
                  value={reportMessage}
                  onChange={(e) => setReportMessage(e.target.value)}
                  placeholder="Any notes for your accountant..."
                  className="w-full p-3 border rounded-md text-sm"
                  rows={3}
                />
              </div>
              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={() => setShowSendModal(false)}>Cancel</Button>
                <Button onClick={sendToAccountant} disabled={sending} className="bg-blue-600 hover:bg-blue-700">
                  {sending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
                  Send Report
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
      
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-blue-50 to-white border-blue-200">
          <CardContent className="p-4">
            <p className="text-sm text-blue-600 font-medium">Total Revenue</p>
            <p className="text-2xl font-bold text-blue-700">${financials?.total_revenue?.toFixed(2) || "0.00"}</p>
            <p className="text-xs text-blue-500">{financials?.order_count || 0} orders</p>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-amber-50 to-white border-amber-200">
          <CardContent className="p-4">
            <p className="text-sm text-amber-600 font-medium">Tax Collected</p>
            <p className="text-2xl font-bold text-amber-700">${financials?.total_tax_collected?.toFixed(2) || "0.00"}</p>
            <p className="text-xs text-amber-500">From customers</p>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-red-50 to-white border-red-200">
          <CardContent className="p-4">
            <p className="text-sm text-red-600 font-medium">Tax to File</p>
            <p className="text-2xl font-bold text-red-700">${financials?.tax_liability?.toFixed(2) || "0.00"}</p>
            <p className="text-xs text-red-500">On selling price</p>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-green-50 to-white border-green-200">
          <CardContent className="p-4">
            <p className="text-sm text-green-600 font-medium">Tax Savings</p>
            <p className="text-2xl font-bold text-green-700">${financials?.tax_profit?.toFixed(2) || "0.00"}</p>
            <p className="text-xs text-green-500">You keep this!</p>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-purple-50 to-white border-purple-200">
          <CardContent className="p-4">
            <p className="text-sm text-purple-600 font-medium">Cost of Goods</p>
            <p className="text-2xl font-bold text-purple-700">${financials?.total_cost_of_goods?.toFixed(2) || "0.00"}</p>
            <p className="text-xs text-purple-500">Your product costs</p>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-emerald-50 to-white border-emerald-200">
          <CardContent className="p-4">
            <p className="text-sm text-emerald-600 font-medium">Net Profit</p>
            <p className="text-2xl font-bold text-emerald-700">${financials?.net_profit?.toFixed(2) || "0.00"}</p>
            <p className="text-xs text-emerald-500">{financials?.profit_margin?.toFixed(1) || 0}% margin</p>
          </CardContent>
        </Card>
      </div>
      
      {/* Detailed Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Revenue Breakdown */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">📊 Revenue Breakdown</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between py-2 border-b">
              <span className="text-gray-600">Products Subtotal (before discounts)</span>
              <span className="font-medium">${financials?.total_subtotal?.toFixed(2) || "0.00"}</span>
            </div>
            <div className="flex justify-between py-2 border-b text-red-600">
              <span>Discounts Given</span>
              <span>-${financials?.total_discounts?.toFixed(2) || "0.00"}</span>
            </div>
            <div className="flex justify-between py-2 border-b font-medium">
              <span>Gross Revenue</span>
              <span>${financials?.gross_revenue?.toFixed(2) || "0.00"}</span>
            </div>
            <div className="flex justify-between py-2 border-b text-amber-600">
              <span>+ Tax Collected (13% HST)</span>
              <span>${financials?.total_tax_collected?.toFixed(2) || "0.00"}</span>
            </div>
            <div className="flex justify-between py-2 font-bold text-lg">
              <span>Total Collected</span>
              <span className="text-blue-600">${financials?.total_revenue?.toFixed(2) || "0.00"}</span>
            </div>
          </CardContent>
        </Card>
        
        {/* Profit Calculation */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">💵 Profit Calculation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between py-2 border-b">
              <span className="text-gray-600">Gross Revenue (after discounts)</span>
              <span className="font-medium">${financials?.gross_revenue?.toFixed(2) || "0.00"}</span>
            </div>
            <div className="flex justify-between py-2 border-b text-purple-600">
              <span>- Cost of Goods Sold (COGS)</span>
              <span>-${financials?.total_cost_of_goods?.toFixed(2) || "0.00"}</span>
            </div>
            <div className="flex justify-between py-2 border-b font-medium">
              <span>Gross Profit</span>
              <span>${financials?.gross_profit?.toFixed(2) || "0.00"}</span>
            </div>
            <div className="flex justify-between py-2 font-bold text-lg bg-emerald-50 -mx-4 px-4 rounded">
              <span>Net Profit</span>
              <span className={financials?.net_profit >= 0 ? "text-emerald-600" : "text-red-600"}>
                ${financials?.net_profit?.toFixed(2) || "0.00"}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Order Details Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">📋 Order Financials</CardTitle>
          <p className="text-sm text-gray-500">Click on shipping cost to update actual courier cost paid</p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left p-3">Order #</th>
                  <th className="text-left p-3">Date</th>
                  <th className="text-right p-3">Revenue</th>
                  <th className="text-right p-3">COGS</th>
                  <th className="text-right p-3">Tax</th>
                  <th className="text-right p-3">Ship Collected</th>
                  <th className="text-right p-3">Ship Paid</th>
                  <th className="text-right p-3 bg-emerald-50">Profit</th>
                </tr>
              </thead>
              <tbody>
                {orders.map(order => (
                  <tr key={order.id} className="border-b hover:bg-gray-50">
                    <td className="p-3 font-medium">{order.order_number}</td>
                    <td className="p-3 text-gray-500">{new Date(order.created_at).toLocaleDateString()}</td>
                    <td className="p-3 text-right">${order.total?.toFixed(2)}</td>
                    <td className="p-3 text-right text-purple-600">${(order.cost_of_goods || 0).toFixed(2)}</td>
                    <td className="p-3 text-right text-amber-600">${order.tax?.toFixed(2)}</td>
                    <td className="p-3 text-right text-green-600">${order.shipping?.toFixed(2)}</td>
                    <td className="p-3 text-right">
                      {editingShippingCost === order.id ? (
                        <div className="flex gap-1 justify-end">
                          <Input
                            type="number"
                            step="0.01"
                            value={shippingCostValue}
                            onChange={(e) => setShippingCostValue(e.target.value)}
                            className="w-20 h-7 text-xs"
                            placeholder="0.00"
                          />
                          <Button size="sm" className="h-7 px-2" onClick={() => updateShippingCost(order.id)}>
                            <Check className="h-3 w-3" />
                          </Button>
                          <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => setEditingShippingCost(null)}>
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      ) : (
                        <button
                          onClick={() => { setEditingShippingCost(order.id); setShippingCostValue(order.shipping_cost_paid || ""); }}
                          className="text-red-600 hover:underline cursor-pointer"
                        >
                          ${(order.shipping_cost_paid || 0).toFixed(2)}
                        </button>
                      )}
                    </td>
                    <td className="p-3 text-right font-bold bg-emerald-50 text-emerald-700">
                      ${(order.profit || 0).toFixed(2)}
                    </td>
                  </tr>
                ))}
                {orders.length === 0 && (
                  <tr>
                    <td colSpan={8} className="p-8 text-center text-gray-500">
                      No paid orders found for this period
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
      
      {/* Business Expenses Section */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-lg">📝 Business Expenses</CardTitle>
            <p className="text-sm text-gray-500">Track all your business expenses for tax deductions</p>
          </div>
          <Button onClick={() => setShowExpenseForm(true)} className="bg-red-600 hover:bg-red-700">
            <Plus className="h-4 w-4 mr-2" />
            Add Expense
          </Button>
        </CardHeader>
        <CardContent>
          {/* Expense Summary by Category */}
          {financials?.expenses_by_category && Object.keys(financials.expenses_by_category).length > 0 && (
            <div className="mb-6 grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(financials.expenses_by_category).map(([cat, amount]) => (
                <div key={cat} className="bg-red-50 p-3 rounded-lg">
                  <p className="text-xs text-red-600 font-medium truncate">{cat}</p>
                  <p className="text-lg font-bold text-red-700">${amount.toFixed(2)}</p>
                </div>
              ))}
            </div>
          )}
          
          {/* Expenses Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left p-3">Date</th>
                  <th className="text-left p-3">Category</th>
                  <th className="text-left p-3">Description</th>
                  <th className="text-left p-3">Vendor</th>
                  <th className="text-right p-3">Amount</th>
                  <th className="text-center p-3">Receipt</th>
                  <th className="text-center p-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {expenses.map(expense => (
                  <tr key={expense.id} className="border-b hover:bg-gray-50">
                    <td className="p-3">{expense.date}</td>
                    <td className="p-3">
                      <span className="bg-red-100 text-red-700 px-2 py-1 rounded text-xs">
                        {expense.category}
                      </span>
                    </td>
                    <td className="p-3">{expense.description}</td>
                    <td className="p-3 text-gray-500">{expense.vendor || "-"}</td>
                    <td className="p-3 text-right font-medium text-red-600">${expense.amount?.toFixed(2)}</td>
                    <td className="p-3 text-center">
                      {expense.receipt_url ? (
                        <a href={expense.receipt_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                          📎 View
                        </a>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="p-3 text-center">
                      <Button variant="ghost" size="sm" onClick={() => deleteExpense(expense.id)} className="text-red-500 hover:text-red-700">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
                {expenses.length === 0 && (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-gray-500">
                      No expenses recorded for this period. Click "Add Expense" to track your business costs.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
      
      {/* Add Expense Modal */}
      {showExpenseForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Receipt className="h-5 w-5 text-red-600" />
                Add Business Expense
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Category *</Label>
                  <select
                    value={expenseForm.category}
                    onChange={(e) => setExpenseForm({ ...expenseForm, category: e.target.value })}
                    className="w-full p-2 border rounded-md"
                  >
                    {expenseCategories.map(cat => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <Label>Date *</Label>
                  <Input
                    type="date"
                    value={expenseForm.date}
                    onChange={(e) => setExpenseForm({ ...expenseForm, date: e.target.value })}
                  />
                </div>
              </div>
              
              <div>
                <Label>Description *</Label>
                <Input
                  value={expenseForm.description}
                  onChange={(e) => setExpenseForm({ ...expenseForm, description: e.target.value })}
                  placeholder="e.g., Monthly hosting fee, Product samples..."
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Amount ($) *</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={expenseForm.amount}
                    onChange={(e) => setExpenseForm({ ...expenseForm, amount: e.target.value })}
                    placeholder="0.00"
                  />
                </div>
                <div>
                  <Label>Vendor/Supplier</Label>
                  <Input
                    value={expenseForm.vendor}
                    onChange={(e) => setExpenseForm({ ...expenseForm, vendor: e.target.value })}
                    placeholder="e.g., Amazon, FedEx..."
                  />
                </div>
              </div>
              
              <div>
                <Label>Receipt (Optional)</Label>
                <div className="flex gap-2">
                  <Input
                    type="file"
                    accept="image/*,.pdf"
                    onChange={handleReceiptUpload}
                    disabled={uploadingReceipt}
                  />
                  {uploadingReceipt && <Loader2 className="h-5 w-5 animate-spin" />}
                </div>
                {expenseForm.receipt_url && (
                  <div className="mt-2 flex items-center gap-2 text-green-600">
                    <Check className="h-4 w-4" />
                    <span className="text-sm">Receipt uploaded</span>
                  </div>
                )}
              </div>
              
              <div>
                <Label>Notes</Label>
                <textarea
                  value={expenseForm.notes}
                  onChange={(e) => setExpenseForm({ ...expenseForm, notes: e.target.value })}
                  className="w-full p-2 border rounded-md text-sm"
                  rows={2}
                  placeholder="Additional notes..."
                />
              </div>
              
              <div className="flex gap-2 justify-end pt-4">
                <Button variant="outline" onClick={() => setShowExpenseForm(false)}>Cancel</Button>
                <Button onClick={submitExpense} className="bg-red-600 hover:bg-red-700">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Expense
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default FinancialsManager;
