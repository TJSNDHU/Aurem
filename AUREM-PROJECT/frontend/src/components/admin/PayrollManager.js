import React, { useState, useEffect, useContext } from "react";
import axios from "axios";
import { toast } from "sonner";
import { StoreSettingsContext } from "@/contexts";
import {
  Plus,
  Trash2,
  Check,
  Loader2,
  Pencil,
  Printer,
  X
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// Get backend URL from environment
const getBackendUrl = () => {
  return process.env.REACT_APP_BACKEND_URL || window.location.origin;
};

const API = `${getBackendUrl()}/api`;

// Store Settings hook
const useStoreSettings = () => useContext(StoreSettingsContext);

// ImageUploader component for logo uploads
const ImageUploader = ({ value, onChange, placeholder = "Enter image URL or upload" }) => {
  const [uploading, setUploading] = useState(false);
  
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const token = localStorage.getItem("reroots_token");
      const response = await axios.post(`${API}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          Authorization: `Bearer ${token}`
        }
      });
      onChange(response.data.url);
      toast.success("Image uploaded successfully!");
    } catch (error) {
      console.error("Upload error:", error);
      toast.error("Failed to upload image");
    } finally {
      setUploading(false);
    }
  };
  
  return (
    <div className="space-y-2">
      <Input
        type="text"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      <div className="flex items-center gap-2">
        <input
          type="file"
          accept="image/*"
          onChange={handleFileUpload}
          className="hidden"
          id="payroll-logo-upload"
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => document.getElementById('payroll-logo-upload')?.click()}
          disabled={uploading}
        >
          {uploading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
          {uploading ? "Uploading..." : "Upload Image"}
        </Button>
      </div>
    </div>
  );
};

const PayrollManager = () => {
  const [employees, setEmployees] = useState([]);
  const [payrollEntries, setPayrollEntries] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeView, setActiveView] = useState("generate"); // "generate", "employees", "history", "settings"
  const [showEmployeeForm, setShowEmployeeForm] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [payPeriodStart, setPayPeriodStart] = useState("");
  const [payPeriodEnd, setPayPeriodEnd] = useState("");
  const [payType, setPayType] = useState("weekly");
  const [employeeHours, setEmployeeHours] = useState({});
  const [generating, setGenerating] = useState(false);
  const { settings } = useStoreSettings();
  
  // Pay Stub Customization Settings
  const [payStubSettings, setPayStubSettings] = useState({
    logo_url: "",
    company_name: "ReRoots Beauty Enhancer",
    company_address: "",
    company_phone: "",
    company_email: "",
    header_text: "",
    footer_text: "This is a computer-generated pay stub.",
    signature_name: "",
    signature_title: "",
    show_signature_line: true,
    accent_color: "#F8A5B8"
  });
  const [savingSettings, setSavingSettings] = useState(false);
  
  // Load pay stub settings from backend on mount
  useEffect(() => {
    const loadPayStubSettings = async () => {
      try {
        const token = localStorage.getItem("reroots_token");
        const res = await axios.get(`${API}/admin/payroll/settings`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.data) {
          setPayStubSettings(prev => ({ ...prev, ...res.data }));
        }
      } catch (error) {
        console.log("Using default pay stub settings");
      }
    };
    loadPayStubSettings();
  }, []);
  
  // Save pay stub settings to backend
  const handleSavePayStubSettings = async () => {
    setSavingSettings(true);
    try {
      const token = localStorage.getItem("reroots_token");
      await axios.post(`${API}/admin/payroll/settings`, payStubSettings, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Pay stub settings saved successfully!");
    } catch (error) {
      toast.error("Failed to save settings");
      console.error("Save settings error:", error);
    } finally {
      setSavingSettings(false);
    }
  };
  
  // New employee form state
  const [newEmployee, setNewEmployee] = useState({
    name: "", email: "", phone: "", role: "Staff", hourly_rate: 0, tax_rate: 15, start_date: ""
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("reroots_token");
      const headers = { Authorization: `Bearer ${token}` };
      
      const [empRes, payRes, sumRes] = await Promise.all([
        axios.get(`${API}/admin/employees`, { headers }),
        axios.get(`${API}/admin/payroll`, { headers }),
        axios.get(`${API}/admin/payroll/summary`, { headers })
      ]);
      
      setEmployees(empRes.data || []);
      setPayrollEntries(payRes.data || []);
      setSummary(sumRes.data || {});
      
      // Initialize employee hours
      const hours = {};
      (empRes.data || []).forEach(emp => {
        hours[emp.id] = { hours_worked: 0, other_deductions: 0, deduction_notes: "" };
      });
      setEmployeeHours(hours);
    } catch (error) {
      console.error("Failed to fetch payroll data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddEmployee = async () => {
    try {
      const token = localStorage.getItem("reroots_token");
      await axios.post(`${API}/admin/employees`, newEmployee, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Employee added!");
      setShowEmployeeForm(false);
      setNewEmployee({ name: "", email: "", phone: "", role: "Staff", hourly_rate: 0, tax_rate: 15, start_date: "" });
      fetchData();
    } catch (error) {
      toast.error("Failed to add employee");
    }
  };

  const handleUpdateEmployee = async () => {
    try {
      const token = localStorage.getItem("reroots_token");
      await axios.put(`${API}/admin/employees/${editingEmployee.id}`, editingEmployee, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Employee updated!");
      setEditingEmployee(null);
      fetchData();
    } catch (error) {
      toast.error("Failed to update employee");
    }
  };

  const handleDeleteEmployee = async (employeeId) => {
    if (!window.confirm("Are you sure you want to delete this employee?")) return;
    try {
      const token = localStorage.getItem("reroots_token");
      await axios.delete(`${API}/admin/employees/${employeeId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Employee deleted");
      fetchData();
    } catch (error) {
      toast.error("Failed to delete employee");
    }
  };

  const handleGeneratePayroll = async () => {
    if (!payPeriodStart || !payPeriodEnd) {
      toast.error("Please select pay period dates");
      return;
    }
    
    const employeeHoursArray = Object.entries(employeeHours)
      .filter(([_, data]) => data.hours_worked > 0)
      .map(([employee_id, data]) => ({
        employee_id,
        hours_worked: data.hours_worked,
        other_deductions: data.other_deductions,
        deduction_notes: data.deduction_notes
      }));
    
    if (employeeHoursArray.length === 0) {
      toast.error("Please enter hours for at least one employee");
      return;
    }
    
    setGenerating(true);
    try {
      const token = localStorage.getItem("reroots_token");
      const res = await axios.post(`${API}/admin/payroll/generate`, {
        pay_period_start: payPeriodStart,
        pay_period_end: payPeriodEnd,
        pay_type: payType,
        employee_hours: employeeHoursArray
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(res.data.message);
      fetchData();
      // Reset hours
      const hours = {};
      employees.forEach(emp => {
        hours[emp.id] = { hours_worked: 0, other_deductions: 0, deduction_notes: "" };
      });
      setEmployeeHours(hours);
    } catch (error) {
      toast.error("Failed to generate payroll");
    } finally {
      setGenerating(false);
    }
  };

  const handleMarkAsPaid = async (payrollId) => {
    try {
      const token = localStorage.getItem("reroots_token");
      await axios.put(`${API}/admin/payroll/${payrollId}/status`, { status: "paid" }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Marked as paid");
      fetchData();
    } catch (error) {
      toast.error("Failed to update status");
    }
  };

  const printPayStub = (entry) => {
    const printWindow = window.open('', '_blank');
    const rawLogo = payStubSettings.logo_url || settings?.site_logo || "https://customer-assets.emergentagent.com/job_a381cf1d-579d-4c54-9ee9-c2aab86c5628/artifacts/2n6enhsj_1769103145313.png";
    // Optimize logo through Cloudinary (max 200px width for print)
    const logo = rawLogo.includes('cloudinary.com') 
      ? rawLogo 
      : `https://res.cloudinary.com/ddpphzqdg/image/fetch/w_200,h_80,c_fit,q_auto,f_auto/${encodeURIComponent(rawLogo)}`;
    const companyName = payStubSettings.company_name || settings?.site_name || "ReRoots Beauty Enhancer";
    const accentColor = payStubSettings.accent_color || "#F8A5B8";
    
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Pay Stub - ${entry.employee_name}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; }
          .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid ${accentColor}; padding-bottom: 20px; margin-bottom: 20px; }
          .logo { height: 70px; max-width: 200px; object-fit: contain; }
          .company-info { text-align: right; }
          .company-name { font-size: 24px; font-weight: bold; color: #2D2A2E; }
          .company-details { font-size: 12px; color: #666; margin-top: 5px; }
          .header-text { text-align: center; font-style: italic; color: #666; margin-bottom: 20px; padding: 10px; background: #f9f9f9; border-radius: 8px; }
          .pay-stub-title { text-align: center; font-size: 28px; font-weight: bold; color: #2D2A2E; margin-bottom: 30px; padding: 15px; background: linear-gradient(135deg, ${accentColor}22 0%, ${accentColor}44 100%); border-radius: 8px; }
          .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 30px; }
          .info-box { background: #f9f9f9; padding: 15px; border-radius: 8px; border-left: 4px solid ${accentColor}; }
          .info-label { font-size: 11px; color: #666; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.5px; }
          .info-value { font-size: 16px; font-weight: bold; color: #2D2A2E; }
          .earnings-table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
          .earnings-table th, .earnings-table td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
          .earnings-table th { background: #2D2A2E; color: white; }
          .earnings-table .amount { text-align: right; }
          .total-row { background: #f0f0f0; font-weight: bold; }
          .net-pay { background: ${accentColor}; color: #2D2A2E; font-size: 20px; }
          .signature-section { margin-top: 50px; display: flex; justify-content: space-between; }
          .signature-box { width: 45%; }
          .signature-line { border-top: 1px solid #333; margin-top: 40px; padding-top: 10px; }
          .signature-name { font-weight: bold; color: #2D2A2E; }
          .signature-title { font-size: 12px; color: #666; }
          .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 2px solid ${accentColor}; }
          .footer-text { color: #666; font-size: 12px; margin-bottom: 10px; }
          .footer-generated { color: #999; font-size: 10px; }
          @media print { body { padding: 20px; } }
        </style>
      </head>
      <body>
        <div class="header">
          <img src="${logo}" alt="Company Logo" class="logo" />
          <div class="company-info">
            <div class="company-name">${companyName}</div>
            ${payStubSettings.company_address ? `<div class="company-details">${payStubSettings.company_address}</div>` : ''}
            ${payStubSettings.company_phone ? `<div class="company-details">📞 ${payStubSettings.company_phone}</div>` : ''}
            ${payStubSettings.company_email ? `<div class="company-details">✉️ ${payStubSettings.company_email}</div>` : ''}
          </div>
        </div>
        
        ${payStubSettings.header_text ? `<div class="header-text">${payStubSettings.header_text}</div>` : ''}
        
        <div class="pay-stub-title">💵 PAY STUB</div>
        
        <div class="info-grid">
          <div class="info-box">
            <div class="info-label">Employee Name</div>
            <div class="info-value">${entry.employee_name}</div>
          </div>
          <div class="info-box">
            <div class="info-label">Pay Period</div>
            <div class="info-value">${entry.pay_period_start} to ${entry.pay_period_end}</div>
          </div>
          <div class="info-box">
            <div class="info-label">Pay Type</div>
            <div class="info-value">${entry.pay_type.charAt(0).toUpperCase() + entry.pay_type.slice(1)}</div>
          </div>
          <div class="info-box">
            <div class="info-label">Pay Date</div>
            <div class="info-value">${entry.paid_date ? new Date(entry.paid_date).toLocaleDateString() : 'Pending'}</div>
          </div>
        </div>
        
        <table class="earnings-table">
          <thead>
            <tr>
              <th>Description</th>
              <th class="amount">Hours/Rate</th>
              <th class="amount">Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Regular Hours</td>
              <td class="amount">${entry.hours_worked} hrs @ $${entry.hourly_rate.toFixed(2)}/hr</td>
              <td class="amount">$${entry.gross_pay.toFixed(2)}</td>
            </tr>
            <tr class="total-row">
              <td colspan="2">Gross Pay</td>
              <td class="amount">$${entry.gross_pay.toFixed(2)}</td>
            </tr>
            <tr>
              <td>Tax Deduction</td>
              <td class="amount"></td>
              <td class="amount">-$${entry.tax_deduction.toFixed(2)}</td>
            </tr>
            ${entry.other_deductions > 0 ? `
            <tr>
              <td>Other Deductions ${entry.deduction_notes ? `(${entry.deduction_notes})` : ''}</td>
              <td class="amount"></td>
              <td class="amount">-$${entry.other_deductions.toFixed(2)}</td>
            </tr>
            ` : ''}
            <tr class="total-row net-pay">
              <td colspan="2">NET PAY</td>
              <td class="amount">$${entry.net_pay.toFixed(2)}</td>
            </tr>
          </tbody>
        </table>
        
        ${payStubSettings.show_signature_line ? `
        <div class="signature-section">
          <div class="signature-box">
            <div class="signature-line">
              <div class="signature-name">${payStubSettings.signature_name || 'Authorized Signature'}</div>
              <div class="signature-title">${payStubSettings.signature_title || 'Manager / HR'}</div>
            </div>
          </div>
          <div class="signature-box">
            <div class="signature-line">
              <div class="signature-name">Employee Signature</div>
              <div class="signature-title">Date: _____________</div>
            </div>
          </div>
        </div>
        ` : ''}
        
        <div class="footer">
          <p class="footer-text">${payStubSettings.footer_text || 'This is a computer-generated pay stub.'}</p>
          <p class="footer-generated">Generated on ${new Date().toLocaleDateString()} at ${new Date().toLocaleTimeString()} | ${companyName}</p>
        </div>
        
        <script>window.onload = function() { window.print(); }</script>
      </body>
      </html>
    `);
    printWindow.document.close();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
            💵 Payroll Management
          </h2>
          <p className="text-[#5A5A5A]">Generate pay stubs, manage employees, and track payments</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
          <CardContent className="p-4">
            <p className="text-sm text-blue-600">Total Employees</p>
            <p className="text-2xl font-bold text-blue-700">{employees.filter(e => e.is_active).length}</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
          <CardContent className="p-4">
            <p className="text-sm text-green-600">Total Paid</p>
            <p className="text-2xl font-bold text-green-700">${(summary?.total_paid || 0).toFixed(2)}</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-yellow-50 to-yellow-100 border-yellow-200">
          <CardContent className="p-4">
            <p className="text-sm text-yellow-600">Pending Payments</p>
            <p className="text-2xl font-bold text-yellow-700">${(summary?.total_pending || 0).toFixed(2)}</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
          <CardContent className="p-4">
            <p className="text-sm text-purple-600">Total Tax Deducted</p>
            <p className="text-2xl font-bold text-purple-700">${(summary?.total_tax_deducted || 0).toFixed(2)}</p>
          </CardContent>
        </Card>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 border-b pb-2 flex-wrap">
        {[
          { id: "generate", label: "📝 Generate Payroll" },
          { id: "employees", label: "👥 Employees" },
          { id: "history", label: "📋 Payroll History" },
          { id: "settings", label: "⚙️ Pay Stub Settings" }
        ].map(tab => (
          <Button
            key={tab.id}
            variant={activeView === tab.id ? "default" : "outline"}
            onClick={() => setActiveView(tab.id)}
            className={activeView === tab.id ? "bg-blue-600 text-white" : ""}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {/* Generate Payroll View */}
      {activeView === "generate" && (
        <Card>
          <CardHeader>
            <CardTitle>Generate Payroll</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Pay Period Selection */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label>Pay Period Start</Label>
                <Input
                  type="date"
                  value={payPeriodStart}
                  onChange={(e) => setPayPeriodStart(e.target.value)}
                />
              </div>
              <div>
                <Label>Pay Period End</Label>
                <Input
                  type="date"
                  value={payPeriodEnd}
                  onChange={(e) => setPayPeriodEnd(e.target.value)}
                />
              </div>
              <div>
                <Label>Pay Type</Label>
                <Select value={payType} onValueChange={setPayType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="biweekly">Bi-Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Employee Hours Table */}
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-[#2D2A2E] text-white">
                  <tr>
                    <th className="p-3 text-left">Employee</th>
                    <th className="p-3 text-left">Role</th>
                    <th className="p-3 text-right">Rate/Hr</th>
                    <th className="p-3 text-right">Tax %</th>
                    <th className="p-3 text-center">Hours Worked</th>
                    <th className="p-3 text-center">Other Deductions</th>
                    <th className="p-3 text-center">Deduction Notes</th>
                    <th className="p-3 text-right">Est. Net Pay</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.filter(e => e.is_active).map(emp => {
                    const hours = employeeHours[emp.id]?.hours_worked || 0;
                    const otherDed = employeeHours[emp.id]?.other_deductions || 0;
                    const gross = hours * emp.hourly_rate;
                    const tax = gross * (emp.tax_rate / 100);
                    const net = gross - tax - otherDed;
                    
                    return (
                      <tr key={emp.id} className="border-b hover:bg-gray-50">
                        <td className="p-3 font-medium">{emp.name}</td>
                        <td className="p-3 text-[#5A5A5A]">{emp.role}</td>
                        <td className="p-3 text-right">${emp.hourly_rate.toFixed(2)}</td>
                        <td className="p-3 text-right">{emp.tax_rate}%</td>
                        <td className="p-3">
                          <Input
                            type="number"
                            min="0"
                            step="0.5"
                            className="w-24 mx-auto text-center"
                            value={employeeHours[emp.id]?.hours_worked || ""}
                            onChange={(e) => setEmployeeHours({
                              ...employeeHours,
                              [emp.id]: { ...employeeHours[emp.id], hours_worked: parseFloat(e.target.value) || 0 }
                            })}
                            placeholder="0"
                          />
                        </td>
                        <td className="p-3">
                          <Input
                            type="number"
                            min="0"
                            step="0.01"
                            className="w-24 mx-auto text-center"
                            value={employeeHours[emp.id]?.other_deductions || ""}
                            onChange={(e) => setEmployeeHours({
                              ...employeeHours,
                              [emp.id]: { ...employeeHours[emp.id], other_deductions: parseFloat(e.target.value) || 0 }
                            })}
                            placeholder="0"
                          />
                        </td>
                        <td className="p-3">
                          <Input
                            type="text"
                            className="w-32 mx-auto text-center text-sm"
                            value={employeeHours[emp.id]?.deduction_notes || ""}
                            onChange={(e) => setEmployeeHours({
                              ...employeeHours,
                              [emp.id]: { ...employeeHours[emp.id], deduction_notes: e.target.value }
                            })}
                            placeholder="Notes..."
                          />
                        </td>
                        <td className="p-3 text-right font-bold text-green-600">
                          ${net > 0 ? net.toFixed(2) : "0.00"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {employees.filter(e => e.is_active).length === 0 && (
              <div className="text-center py-8 text-[#5A5A5A]">
                <p>No employees found. Add employees first in the &quot;Employees&quot; tab.</p>
              </div>
            )}

            <Button 
              onClick={handleGeneratePayroll} 
              disabled={generating || employees.filter(e => e.is_active).length === 0}
              className="w-full bg-blue-600 hover:bg-blue-700"
            >
              {generating ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Generating...</> : "💵 Generate Payroll"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Employees View */}
      {activeView === "employees" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>👥 Employees</CardTitle>
            <Button onClick={() => setShowEmployeeForm(true)} className="bg-blue-600 hover:bg-blue-700">
              <Plus className="h-4 w-4 mr-2" /> Add Employee
            </Button>
          </CardHeader>
          <CardContent>
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-[#2D2A2E] text-white">
                  <tr>
                    <th className="p-3 text-left">Name</th>
                    <th className="p-3 text-left">Role</th>
                    <th className="p-3 text-left">Contact</th>
                    <th className="p-3 text-right">Rate/Hr</th>
                    <th className="p-3 text-right">Tax Rate</th>
                    <th className="p-3 text-center">Status</th>
                    <th className="p-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map(emp => (
                    <tr key={emp.id} className="border-b hover:bg-gray-50">
                      <td className="p-3 font-medium">{emp.name}</td>
                      <td className="p-3 text-[#5A5A5A]">{emp.role}</td>
                      <td className="p-3 text-sm text-[#5A5A5A]">
                        {emp.email && <div>{emp.email}</div>}
                        {emp.phone && <div>{emp.phone}</div>}
                      </td>
                      <td className="p-3 text-right font-medium">${emp.hourly_rate?.toFixed(2)}</td>
                      <td className="p-3 text-right">{emp.tax_rate}%</td>
                      <td className="p-3 text-center">
                        <Badge variant={emp.is_active ? "default" : "secondary"}>
                          {emp.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </td>
                      <td className="p-3 text-center">
                        <div className="flex justify-center gap-2">
                          <Button size="sm" variant="outline" onClick={() => setEditingEmployee(emp)}>
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button size="sm" variant="outline" className="text-red-500" onClick={() => handleDeleteEmployee(emp.id)}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {employees.length === 0 && (
              <div className="text-center py-8 text-[#5A5A5A]">
                <p>No employees yet. Click &quot;Add Employee&quot; to get started.</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Payroll History View */}
      {activeView === "history" && (
        <Card>
          <CardHeader>
            <CardTitle>📋 Payroll History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-[#2D2A2E] text-white">
                  <tr>
                    <th className="p-3 text-left">Employee</th>
                    <th className="p-3 text-left">Pay Period</th>
                    <th className="p-3 text-right">Hours</th>
                    <th className="p-3 text-right">Gross</th>
                    <th className="p-3 text-right">Tax</th>
                    <th className="p-3 text-right">Net Pay</th>
                    <th className="p-3 text-center">Status</th>
                    <th className="p-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {payrollEntries.map(entry => (
                    <tr key={entry.id} className="border-b hover:bg-gray-50">
                      <td className="p-3 font-medium">{entry.employee_name}</td>
                      <td className="p-3 text-sm text-[#5A5A5A]">
                        {entry.pay_period_start} → {entry.pay_period_end}
                        <div className="text-xs text-blue-500">{entry.pay_type}</div>
                      </td>
                      <td className="p-3 text-right">{entry.hours_worked}</td>
                      <td className="p-3 text-right">${entry.gross_pay?.toFixed(2)}</td>
                      <td className="p-3 text-right text-red-500">-${entry.tax_deduction?.toFixed(2)}</td>
                      <td className="p-3 text-right font-bold text-green-600">${entry.net_pay?.toFixed(2)}</td>
                      <td className="p-3 text-center">
                        <Badge variant={entry.status === "paid" ? "default" : "secondary"} 
                               className={entry.status === "paid" ? "bg-green-500" : "bg-yellow-500"}>
                          {entry.status === "paid" ? "✓ Paid" : "⏳ Pending"}
                        </Badge>
                      </td>
                      <td className="p-3 text-center">
                        <div className="flex justify-center gap-1">
                          <Button size="sm" variant="outline" onClick={() => printPayStub(entry)} title="Print Pay Stub">
                            <Printer className="h-3 w-3" />
                          </Button>
                          {entry.status !== "paid" && (
                            <Button size="sm" variant="outline" className="text-green-600" 
                                    onClick={() => handleMarkAsPaid(entry.id)} title="Mark as Paid">
                              <Check className="h-3 w-3" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {payrollEntries.length === 0 && (
              <div className="text-center py-8 text-[#5A5A5A]">
                <p>No payroll entries yet. Generate payroll from the &quot;Generate Payroll&quot; tab.</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Pay Stub Settings View */}
      {activeView === "settings" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span>⚙️</span> Pay Stub Customization
            </CardTitle>
            <p className="text-sm text-[#5A5A5A]">Customize the look and content of your generated pay stubs</p>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Company Information */}
            <div className="space-y-4">
              <h3 className="font-semibold text-lg border-b pb-2">🏢 Company Information</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Company Name</Label>
                  <Input
                    value={payStubSettings.company_name}
                    onChange={(e) => setPayStubSettings({...payStubSettings, company_name: e.target.value})}
                    placeholder="Your Company Name"
                  />
                </div>
                <div>
                  <Label>Company Logo</Label>
                  <ImageUploader
                    value={payStubSettings.logo_url}
                    onChange={(url) => setPayStubSettings({...payStubSettings, logo_url: url})}
                    placeholder="Upload logo or enter URL"
                  />
                  {payStubSettings.logo_url && (
                    <div className="mt-2 p-2 border rounded bg-gray-50 flex items-center gap-3">
                      <img src={payStubSettings.logo_url} alt="Logo Preview" className="h-12 object-contain" onError={(e) => e.target.style.display='none'} />
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="text-red-500 hover:text-red-700"
                        onClick={() => setPayStubSettings({...payStubSettings, logo_url: ""})}
                      >
                        <X className="h-4 w-4" /> Remove
                      </Button>
                    </div>
                  )}
                </div>
              </div>
              <div>
                <Label>Company Address</Label>
                <Input
                  value={payStubSettings.company_address}
                  onChange={(e) => setPayStubSettings({...payStubSettings, company_address: e.target.value})}
                  placeholder="123 Main St, City, State, ZIP"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Company Phone</Label>
                  <Input
                    value={payStubSettings.company_phone}
                    onChange={(e) => setPayStubSettings({...payStubSettings, company_phone: e.target.value})}
                    placeholder="+1 (555) 123-4567"
                  />
                </div>
                <div>
                  <Label>Company Email</Label>
                  <Input
                    type="email"
                    value={payStubSettings.company_email}
                    onChange={(e) => setPayStubSettings({...payStubSettings, company_email: e.target.value})}
                    placeholder="payroll@company.com"
                  />
                </div>
              </div>
            </div>

            {/* Header & Footer Customization */}
            <div className="space-y-4">
              <h3 className="font-semibold text-lg border-b pb-2">📝 Header & Footer Text</h3>
              <div>
                <Label>Custom Header Text</Label>
                <textarea
                  className="w-full border rounded-md p-2 min-h-[80px] text-sm"
                  value={payStubSettings.header_text}
                  onChange={(e) => setPayStubSettings({...payStubSettings, header_text: e.target.value})}
                  placeholder="Optional text to appear below the company header (e.g., 'Confidential - Employee Pay Statement')"
                />
              </div>
              <div>
                <Label>Custom Footer Text</Label>
                <textarea
                  className="w-full border rounded-md p-2 min-h-[80px] text-sm"
                  value={payStubSettings.footer_text}
                  onChange={(e) => setPayStubSettings({...payStubSettings, footer_text: e.target.value})}
                  placeholder="Footer disclaimer text (e.g., 'This is a computer-generated pay stub.')"
                />
              </div>
            </div>

            {/* Signature Section */}
            <div className="space-y-4">
              <h3 className="font-semibold text-lg border-b pb-2">✍️ Signature Section</h3>
              <div className="flex items-center gap-2 mb-4">
                <input
                  type="checkbox"
                  id="show_signature"
                  checked={payStubSettings.show_signature_line}
                  onChange={(e) => setPayStubSettings({...payStubSettings, show_signature_line: e.target.checked})}
                />
                <Label htmlFor="show_signature">Show signature lines on pay stub</Label>
              </div>
              {payStubSettings.show_signature_line && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label>Authorized Signatory Name</Label>
                    <Input
                      value={payStubSettings.signature_name}
                      onChange={(e) => setPayStubSettings({...payStubSettings, signature_name: e.target.value})}
                      placeholder="e.g., Jane Smith"
                    />
                  </div>
                  <div>
                    <Label>Signatory Title</Label>
                    <Input
                      value={payStubSettings.signature_title}
                      onChange={(e) => setPayStubSettings({...payStubSettings, signature_title: e.target.value})}
                      placeholder="e.g., HR Manager"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Styling Options */}
            <div className="space-y-4">
              <h3 className="font-semibold text-lg border-b pb-2">🎨 Styling</h3>
              <div className="flex items-center gap-4">
                <div>
                  <Label>Accent Color</Label>
                  <div className="flex items-center gap-2 mt-1">
                    <input
                      type="color"
                      value={payStubSettings.accent_color}
                      onChange={(e) => setPayStubSettings({...payStubSettings, accent_color: e.target.value})}
                      className="w-12 h-10 rounded border cursor-pointer"
                    />
                    <Input
                      value={payStubSettings.accent_color}
                      onChange={(e) => setPayStubSettings({...payStubSettings, accent_color: e.target.value})}
                      className="w-28"
                      placeholder="#F8A5B8"
                    />
                  </div>
                </div>
                <div className="flex-1">
                  <Label>Preview</Label>
                  <div className="mt-1 p-3 border rounded flex items-center gap-2" style={{borderColor: payStubSettings.accent_color, backgroundColor: `${payStubSettings.accent_color}22`}}>
                    <div className="w-4 h-4 rounded" style={{backgroundColor: payStubSettings.accent_color}}></div>
                    <span className="text-sm">This is how your accent color will look</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Save Button */}
            <div className="flex justify-end gap-3 pt-4 border-t">
              <Button 
                variant="outline" 
                onClick={() => setPayStubSettings({
                  logo_url: "",
                  company_name: "ReRoots Beauty Enhancer",
                  company_address: "",
                  company_phone: "",
                  company_email: "",
                  header_text: "",
                  footer_text: "This is a computer-generated pay stub.",
                  signature_name: "",
                  signature_title: "",
                  show_signature_line: true,
                  accent_color: "#F8A5B8"
                })}
              >
                Reset to Defaults
              </Button>
              <Button 
                className="bg-blue-600 hover:bg-blue-700"
                onClick={handleSavePayStubSettings}
                disabled={savingSettings}
              >
                {savingSettings ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving...</> : "💾 Save Settings"}
              </Button>
            </div>

            {/* Preview Section */}
            <div className="mt-6 p-4 border-2 border-dashed rounded-lg bg-gray-50">
              <h4 className="font-semibold mb-3">📄 Pay Stub Preview</h4>
              <p className="text-sm text-[#5A5A5A] mb-4">This is a simplified preview. Generate a pay stub from the History tab to see the full design.</p>
              <div className="bg-white p-4 rounded border shadow-sm">
                <div className="flex justify-between items-center border-b-2 pb-3 mb-3" style={{borderColor: payStubSettings.accent_color}}>
                  {payStubSettings.logo_url ? (
                    <img src={payStubSettings.logo_url} alt="Logo" className="h-10 object-contain" onError={(e) => e.target.src='https://via.placeholder.com/100x40?text=Logo'} />
                  ) : (
                    <div className="text-gray-400 text-sm">[Company Logo]</div>
                  )}
                  <div className="text-right">
                    <div className="font-bold text-lg">{payStubSettings.company_name || "Company Name"}</div>
                    {payStubSettings.company_address && <div className="text-xs text-gray-500">{payStubSettings.company_address}</div>}
                  </div>
                </div>
                {payStubSettings.header_text && (
                  <div className="text-center text-sm italic text-gray-600 bg-gray-50 p-2 rounded mb-3">{payStubSettings.header_text}</div>
                )}
                <div className="text-center font-bold text-xl mb-4 p-2 rounded" style={{backgroundColor: `${payStubSettings.accent_color}33`}}>
                  💵 PAY STUB
                </div>
                <div className="text-center text-xs text-gray-400">[Employee Details & Earnings Table]</div>
                {payStubSettings.footer_text && (
                  <div className="mt-4 pt-3 border-t text-center text-xs text-gray-500" style={{borderColor: payStubSettings.accent_color}}>
                    {payStubSettings.footer_text}
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Add Employee Modal */}
      {showEmployeeForm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>Add New Employee</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Full Name *</Label>
                <Input
                  value={newEmployee.name}
                  onChange={(e) => setNewEmployee({ ...newEmployee, name: e.target.value })}
                  placeholder="John Doe"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Email</Label>
                  <Input
                    type="email"
                    value={newEmployee.email}
                    onChange={(e) => setNewEmployee({ ...newEmployee, email: e.target.value })}
                    placeholder="john@example.com"
                  />
                </div>
                <div>
                  <Label>Phone</Label>
                  <Input
                    value={newEmployee.phone}
                    onChange={(e) => setNewEmployee({ ...newEmployee, phone: e.target.value })}
                    placeholder="+1234567890"
                  />
                </div>
              </div>
              <div>
                <Label>Role</Label>
                <Input
                  value={newEmployee.role}
                  onChange={(e) => setNewEmployee({ ...newEmployee, role: e.target.value })}
                  placeholder="e.g. Sales Associate"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Hourly Rate ($) *</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={newEmployee.hourly_rate}
                    onChange={(e) => setNewEmployee({ ...newEmployee, hourly_rate: parseFloat(e.target.value) || 0 })}
                  />
                </div>
                <div>
                  <Label>Tax Rate (%)</Label>
                  <Input
                    type="number"
                    min="0"
                    max="50"
                    value={newEmployee.tax_rate}
                    onChange={(e) => setNewEmployee({ ...newEmployee, tax_rate: parseFloat(e.target.value) || 15 })}
                  />
                </div>
              </div>
              <div>
                <Label>Start Date</Label>
                <Input
                  type="date"
                  value={newEmployee.start_date}
                  onChange={(e) => setNewEmployee({ ...newEmployee, start_date: e.target.value })}
                />
              </div>
              <div className="flex gap-2 pt-4">
                <Button variant="outline" className="flex-1" onClick={() => setShowEmployeeForm(false)}>
                  Cancel
                </Button>
                <Button className="flex-1 bg-blue-600 hover:bg-blue-700" onClick={handleAddEmployee}>
                  Add Employee
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Edit Employee Modal */}
      {editingEmployee && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>Edit Employee</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Full Name *</Label>
                <Input
                  value={editingEmployee.name}
                  onChange={(e) => setEditingEmployee({ ...editingEmployee, name: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Email</Label>
                  <Input
                    type="email"
                    value={editingEmployee.email || ""}
                    onChange={(e) => setEditingEmployee({ ...editingEmployee, email: e.target.value })}
                  />
                </div>
                <div>
                  <Label>Phone</Label>
                  <Input
                    value={editingEmployee.phone || ""}
                    onChange={(e) => setEditingEmployee({ ...editingEmployee, phone: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <Label>Role</Label>
                <Input
                  value={editingEmployee.role}
                  onChange={(e) => setEditingEmployee({ ...editingEmployee, role: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Hourly Rate ($) *</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={editingEmployee.hourly_rate}
                    onChange={(e) => setEditingEmployee({ ...editingEmployee, hourly_rate: parseFloat(e.target.value) || 0 })}
                  />
                </div>
                <div>
                  <Label>Tax Rate (%)</Label>
                  <Input
                    type="number"
                    min="0"
                    max="50"
                    value={editingEmployee.tax_rate}
                    onChange={(e) => setEditingEmployee({ ...editingEmployee, tax_rate: parseFloat(e.target.value) || 15 })}
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={editingEmployee.is_active}
                  onChange={(e) => setEditingEmployee({ ...editingEmployee, is_active: e.target.checked })}
                />
                <Label htmlFor="is_active">Active Employee</Label>
              </div>
              <div className="flex gap-2 pt-4">
                <Button variant="outline" className="flex-1" onClick={() => setEditingEmployee(null)}>
                  Cancel
                </Button>
                <Button className="flex-1 bg-blue-600 hover:bg-blue-700" onClick={handleUpdateEmployee}>
                  Save Changes
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default PayrollManager;
