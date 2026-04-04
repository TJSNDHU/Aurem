/**
 * Sales Pipeline Dashboard
 * Complete view: Scan → Decision Maker → Proposal → Contract → Onboarding
 */

import React, { useState, useEffect } from 'react';
import { 
  Search, Users, FileText, FileSignature, Rocket, 
  ChevronRight, CheckCircle, Clock, AlertCircle, Download,
  Mail, Phone, Linkedin, TrendingUp, Target, Building2,
  Sparkles, ExternalLink
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const SalesPipelineDashboard = ({ token }) => {
  const [selectedScan, setSelectedScan] = useState(null);
  const [decisionMakers, setDecisionMakers] = useState([]);
  const [proposal, setProposal] = useState(null);
  const [contract, setContract] = useState(null);
  const [onboarding, setOnboarding] = useState(null);
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [recentScans, setRecentScans] = useState([]);

  useEffect(() => {
    fetchRecentScans();
  }, []);

  const fetchRecentScans = async () => {
    try {
      const response = await fetch(`${API_URL}/api/scanner/scans`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setRecentScans(data.scans || []);
      }
    } catch (err) {
      console.error('Failed to fetch scans:', err);
    }
  };

  const findDecisionMakers = async (scan) => {
    setLoading(true);
    try {
      const domain = new URL(scan.website_url).hostname.replace('www.', '');
      
      const response = await fetch(`${API_URL}/api/pipeline/find-decision-makers`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          scan_id: scan.scan_id,
          company_domain: domain
        })
      });

      if (response.ok) {
        const data = await response.json();
        setDecisionMakers(data.decision_makers || []);
        setCurrentStep(2);
      }
    } catch (err) {
      console.error('Decision maker search failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const generateProposal = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/pipeline/generate-proposal`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          scan_id: selectedScan.scan_id,
          customer_name: decisionMakers[0]?.name || 'Prospect',
          customer_company: new URL(selectedScan.website_url).hostname,
          selected_tier: 'business'
        })
      });

      if (response.ok) {
        const data = await response.json();
        setProposal(data);
        setCurrentStep(3);
      }
    } catch (err) {
      console.error('Proposal generation failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const generateContract = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/pipeline/generate-contract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          proposal_id: proposal.proposal_id,
          customer_signature: decisionMakers[0]?.name || 'Authorized Signatory',
          start_date: new Date().toISOString().split('T')[0]
        })
      });

      if (response.ok) {
        const data = await response.json();
        setContract(data);
        setCurrentStep(4);
        
        // Fetch onboarding status
        if (data.contract_id) {
          fetchOnboardingStatus(data.contract_id);
        }
      }
    } catch (err) {
      console.error('Contract generation failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchOnboardingStatus = async (contractId) => {
    try {
      const response = await fetch(`${API_URL}/api/pipeline/onboarding-status/${contractId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setOnboarding(data.onboarding);
        setCurrentStep(5);
      }
    } catch (err) {
      console.error('Onboarding status fetch failed:', err);
    }
  };

  const getPowerBadge = (power) => {
    const colors = {
      high: 'bg-green-500/20 text-green-400 border-green-500/30',
      medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      low: 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    };
    return colors[power] || colors.low;
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#050505] p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-light text-[#F4F4F4] tracking-wider mb-2">Sales Pipeline</h1>
          <p className="text-sm text-[#666]">
            Complete journey: Scan → Decision Maker → Proposal → Contract → Onboarding
          </p>
        </div>

        {/* Pipeline Steps */}
        <div className="mb-8 p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
          <div className="flex items-center justify-between">
            {[
              { num: 1, label: 'Scan', icon: Search, active: currentStep >= 1 },
              { num: 2, label: 'Decision Maker', icon: Users, active: currentStep >= 2 },
              { num: 3, label: 'Proposal', icon: FileText, active: currentStep >= 3 },
              { num: 4, label: 'Contract', icon: FileSignature, active: currentStep >= 4 },
              { num: 5, label: 'Onboarding', icon: Rocket, active: currentStep >= 5 }
            ].map((step, idx, arr) => (
              <React.Fragment key={step.num}>
                <div className="flex flex-col items-center">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center mb-2 ${
                    step.active 
                      ? 'bg-gradient-to-r from-[#D4AF37] to-[#8B7355]' 
                      : 'bg-[#1A1A1A] border border-[#252525]'
                  }`}>
                    <step.icon className={`w-5 h-5 ${step.active ? 'text-[#050505]' : 'text-[#555]'}`} />
                  </div>
                  <span className={`text-xs ${step.active ? 'text-[#F4F4F4]' : 'text-[#666]'}`}>
                    {step.label}
                  </span>
                </div>
                {idx < arr.length - 1 && (
                  <ChevronRight className={`w-5 h-5 ${currentStep > step.num ? 'text-[#D4AF37]' : 'text-[#333]'}`} />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Step 1: Select Scan */}
        {currentStep === 1 && (
          <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
            <h2 className="text-lg font-medium text-[#F4F4F4] mb-4 flex items-center gap-2">
              <Search className="w-5 h-5 text-[#D4AF37]" />
              Select a Customer Scan
            </h2>
            
            {recentScans.length === 0 ? (
              <div className="text-center py-12">
                <Search className="w-12 h-12 text-[#333] mx-auto mb-4" />
                <p className="text-sm text-[#666] mb-4">No scans found. Scan a customer website first.</p>
                <button className="px-4 py-2 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded-lg text-sm font-medium hover:opacity-90">
                  Go to Scanner
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                {recentScans.slice(0, 6).map((scan) => (
                  <div
                    key={scan.scan_id}
                    onClick={() => {
                      setSelectedScan(scan);
                      findDecisionMakers(scan);
                    }}
                    className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg cursor-pointer hover:border-[#D4AF37]/30 transition-all"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <h3 className="text-sm font-medium text-[#F4F4F4] mb-1">{scan.website_url}</h3>
                        <p className="text-xs text-[#666]">{new Date(scan.scan_date).toLocaleDateString()}</p>
                      </div>
                      <div className={`text-2xl font-bold ${
                        scan.overall_score >= 80 ? 'text-green-400' : 
                        scan.overall_score >= 60 ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {scan.overall_score}
                      </div>
                    </div>
                    <div className="flex gap-2 text-xs">
                      <span className="px-2 py-1 bg-red-500/10 text-red-400 rounded">
                        {scan.critical_issues} Critical
                      </span>
                      <span className="px-2 py-1 bg-yellow-500/10 text-yellow-400 rounded">
                        {scan.issues_found} Total
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 2: Decision Makers */}
        {currentStep === 2 && decisionMakers.length > 0 && (
          <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
            <h2 className="text-lg font-medium text-[#F4F4F4] mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-[#D4AF37]" />
              Decision Makers Found
            </h2>

            <div className="space-y-3 mb-6">
              {decisionMakers.map((dm, idx) => (
                <div key={idx} className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-gradient-to-r from-[#D4AF37] to-[#8B7355] flex items-center justify-center text-[#050505] font-bold">
                      {dm.name.charAt(0)}
                    </div>
                    <div>
                      <h3 className="text-sm font-medium text-[#F4F4F4]">{dm.name}</h3>
                      <p className="text-xs text-[#888]">{dm.title}</p>
                      <div className="flex gap-2 mt-1">
                        {dm.email && (
                          <a href={`mailto:${dm.email}`} className="text-xs text-[#64C8FF] hover:underline flex items-center gap-1">
                            <Mail className="w-3 h-3" /> {dm.email}
                          </a>
                        )}
                        {dm.linkedin && (
                          <a href={dm.linkedin} target="_blank" rel="noopener noreferrer" className="text-xs text-[#64C8FF] hover:underline flex items-center gap-1">
                            <Linkedin className="w-3 h-3" /> LinkedIn
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className={`px-3 py-1 rounded-full border text-xs font-medium ${getPowerBadge(dm.decision_power)}`}>
                    {dm.decision_power.toUpperCase()} Power
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={generateProposal}
              disabled={loading}
              className="w-full px-4 py-3 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded-lg font-medium hover:opacity-90 transition-all disabled:opacity-50"
            >
              {loading ? 'Generating Proposal...' : 'Generate Proposal'}
            </button>
          </div>
        )}

        {/* Step 3: Proposal */}
        {currentStep >= 3 && proposal && (
          <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg mb-6">
            <h2 className="text-lg font-medium text-[#F4F4F4] mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-[#D4AF37]" />
              Proposal Generated
            </h2>

            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg">
                <div className="text-xs text-[#666] mb-1">Monthly Fee</div>
                <div className="text-2xl font-bold text-[#D4AF37]">${proposal.pricing?.monthly_fee}</div>
              </div>
              <div className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg">
                <div className="text-xs text-[#666] mb-1">Setup Fee</div>
                <div className="text-2xl font-bold text-[#F4F4F4]">${proposal.pricing?.setup_fee}</div>
              </div>
              <div className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg">
                <div className="text-xs text-[#666] mb-1">Annual Savings</div>
                <div className="text-2xl font-bold text-green-400">{proposal.value_proposition?.annual_savings}</div>
              </div>
            </div>

            <div className="flex gap-3">
              <a
                href={`${API_URL}${proposal.pdf_url}`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-[#1A1A1A] border border-[#252525] text-[#F4F4F4] rounded-lg text-sm hover:border-[#D4AF37]/30 transition-all flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download PDF
              </a>
              
              {currentStep === 3 && (
                <button
                  onClick={generateContract}
                  disabled={loading}
                  className="flex-1 px-4 py-2 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded-lg font-medium hover:opacity-90 transition-all disabled:opacity-50"
                >
                  {loading ? 'Generating Contract...' : 'Generate Contract'}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Step 4: Contract */}
        {currentStep >= 4 && contract && (
          <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg mb-6">
            <h2 className="text-lg font-medium text-[#F4F4F4] mb-4 flex items-center gap-2">
              <FileSignature className="w-5 h-5 text-[#D4AF37]" />
              Contract Ready
            </h2>

            <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg mb-4 flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-green-400" />
              <div>
                <p className="text-sm text-green-400 font-medium">Contract Generated</p>
                <p className="text-xs text-green-400/70">ID: {contract.contract_id}</p>
              </div>
            </div>

            <a
              href={`${API_URL}/api/pipeline/contracts/${contract.contract_id}/pdf`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 bg-[#1A1A1A] border border-[#252525] text-[#F4F4F4] rounded-lg text-sm hover:border-[#D4AF37]/30 transition-all"
            >
              <Download className="w-4 h-4" />
              Download Contract
            </a>
          </div>
        )}

        {/* Step 5: Onboarding */}
        {currentStep >= 5 && onboarding && (
          <div className="p-6 bg-gradient-to-br from-[#D4AF37]/10 to-[#8B7355]/10 border border-[#D4AF37]/30 rounded-lg">
            <h2 className="text-lg font-medium text-[#D4AF37] mb-4 flex items-center gap-2">
              <Rocket className="w-5 h-5" />
              Onboarding in Progress
            </h2>

            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-[#F4F4F4]">Progress</span>
                <span className="text-sm font-medium text-[#D4AF37]">{onboarding.progress?.percentage}%</span>
              </div>
              <div className="w-full h-2 bg-[#1A1A1A] rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-[#D4AF37] to-[#8B7355] transition-all duration-500"
                  style={{ width: `${onboarding.progress?.percentage}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              {onboarding.steps?.map((step, idx) => (
                <div key={idx} className="flex items-center gap-3 p-3 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
                  {step.status === 'completed' ? (
                    <CheckCircle className="w-5 h-5 text-green-400" />
                  ) : step.status === 'pending' ? (
                    <Clock className="w-5 h-5 text-yellow-400" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-gray-400" />
                  )}
                  <span className={`text-sm ${step.status === 'completed' ? 'text-[#F4F4F4]' : 'text-[#888]'}`}>
                    {step.name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SalesPipelineDashboard;
