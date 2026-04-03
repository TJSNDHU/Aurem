import React from 'react';
import { Shield, Download, Clock, CheckCircle2, Sparkles, CalendarDays, MessageCircle } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';

// 12-Week Milestones for tracking calendar
const MILESTONES = [
  { week: 1, phase: 'Adjustment', title: 'Day 1-7: The Initiation Phase', 
    lookFor: ['Initial tingling/warmth (normal)', 'Temporary increase in oiliness', 'Skin may feel "different"'],
    tip: 'Start with Step 1 alone for 3 nights before adding Step 2' },
  { week: 2, phase: 'Adjustment', title: 'Day 8-14: Cellular Acceleration', 
    lookFor: ['Possible micro-purging (small breakouts)', 'Increased cell turnover visible', 'Skin texture feels "gritty"'],
    tip: 'This is the PDRN activating dormant follicles - not new acne' },
  { week: 4, phase: 'Strengthening', title: 'Day 15-30: The Barrier Rebuild', 
    lookFor: ['Purging subsides', 'First signs of glow', 'Texture smoothing begins'],
    tip: 'Increase to nightly use if tolerated' },
  { week: 6, phase: 'Strengthening', title: 'Day 31-45: Pigment Blockade Active', 
    lookFor: ['Dark spots beginning to lighten', 'Even skin tone emerging', 'Fine lines softening'],
    tip: 'Take progress photos in same lighting' },
  { week: 8, phase: 'Transformation', title: 'Day 46-60: Visible Transformation', 
    lookFor: ['Noticeable pigment reduction', 'Firmer skin texture', 'Others start noticing'],
    tip: 'Consider adding Vitamin C in AM routine' },
  { week: 12, phase: 'Maintenance', title: 'Day 61-90: Protocol Complete', 
    lookFor: ['Full pigment correction', 'Lasting barrier strength', 'New skin generation cycle complete'],
    tip: 'Transition to maintenance (3x weekly)' },
];

const ComboSuccessMessage = ({ combo, orderNumber }) => {
  const totalActive = combo?.total_active_percent || 55.02;
  
  const downloadTrackingCalendar = () => {
    // Create a simple text-based tracking calendar
    const calendarContent = `
AURA-GEN 12-WEEK TRANSFORMATION PROTOCOL
========================================
Order: ${orderNumber || 'N/A'}
Protocol: ${combo?.name || 'Resurface & Rebuild System'}
Total Active Concentration: ${totalActive}%

YOUR TRANSFORMATION MILESTONES:
-------------------------------

${MILESTONES.map(m => `
WEEK ${m.week}: ${m.title}
Phase: ${m.phase}
What to Look For:
${m.lookFor.map(l => `  ✓ ${l}`).join('\n')}
Pro Tip: ${m.tip}
`).join('\n')}

DAILY TRACKING SHEET
--------------------
Date: ___________
Redness Level (1-5): ___
Texture Smoothness (1-5): ___
Pigment Clarity (1-5): ___
Notes: ________________________________

IMPORTANT REMINDERS:
- SPF 30+ MANDATORY every morning
- Apply in PM routine only
- Wait 60-90 seconds between Step 1 and Step 2
- Start 3x weekly, increase to nightly as tolerated

For questions, contact our AI Protocol Support: support@reroots.ca
`;
    
    const blob = new Blob([calendarContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '12-Week-Transformation-Protocol.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="overflow-hidden border-2 border-green-200 shadow-xl">
      {/* Success Header */}
      <div className="bg-gradient-to-r from-emerald-500 to-green-400 p-6 text-white">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center">
            <Shield className="h-7 w-7" />
          </div>
          <div>
            <h2 className="text-2xl font-bold">Your Transformation Protocol is Locked In.</h2>
            <p className="text-emerald-100">Clinical-Grade Skincare Activated</p>
          </div>
        </div>
      </div>

      <CardContent className="p-6">
        {/* Main Message */}
        <div className="mb-6 p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl border border-purple-200">
          <p className="text-gray-700 leading-relaxed">
            Thank you for choosing the <strong className="text-purple-700">{combo?.name || 'AURA-GEN Resurface & Rebuild System'}</strong>. 
            You have just secured a cumulative <strong className="text-amber-600">{totalActive}% active treatment</strong>—one 
            of the highest concentrations available without a prescription.
          </p>
        </div>

        {/* What Happens Next */}
        <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-purple-500" />
          What Happens Next
        </h3>

        <div className="grid md:grid-cols-3 gap-4 mb-6">
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="h-5 w-5 text-blue-600" />
              <span className="font-semibold text-blue-800">Preparation</span>
            </div>
            <p className="text-sm text-blue-700">
              Your skin is about to undergo a 12-week reprogramming phase. Expect adjustment in weeks 1-2.
            </p>
          </div>

          <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
            <div className="flex items-center gap-2 mb-2">
              <CalendarDays className="h-5 w-5 text-purple-600" />
              <span className="font-semibold text-purple-800">Digital Guide</span>
            </div>
            <p className="text-sm text-purple-700">
              Download your 12-Week Transformation Calendar with nightly tracking sheets.
            </p>
          </div>

          <div className="p-4 bg-green-50 rounded-lg border border-green-200">
            <div className="flex items-center gap-2 mb-2">
              <MessageCircle className="h-5 w-5 text-green-600" />
              <span className="font-semibold text-green-800">Clinical Support</span>
            </div>
            <p className="text-sm text-green-700">
              Our AI-powered protocol support is available 24/7 for adjustment questions.
            </p>
          </div>
        </div>

        {/* 12-Week Timeline Preview */}
        <div className="mb-6 p-4 bg-gray-50 rounded-xl">
          <h4 className="font-semibold text-gray-900 mb-3">12-Week Timeline Preview</h4>
          <div className="flex items-center gap-2 overflow-x-auto pb-2">
            {['Adjustment', 'Strengthening', 'Transformation', 'Maintenance'].map((phase, idx) => (
              <Badge 
                key={phase}
                className={`whitespace-nowrap ${
                  idx === 0 ? 'bg-amber-500' :
                  idx === 1 ? 'bg-blue-500' :
                  idx === 2 ? 'bg-purple-500' :
                  'bg-green-500'
                } text-white`}
              >
                {phase}
              </Badge>
            ))}
          </div>
          <div className="mt-3 space-y-2">
            {MILESTONES.slice(0, 3).map((m, idx) => (
              <div key={idx} className="flex items-start gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5" />
                <div>
                  <span className="text-sm font-medium text-gray-800">Week {m.week}:</span>
                  <span className="text-sm text-gray-600 ml-1">{m.lookFor[0]}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Download Button */}
        <Button 
          onClick={downloadTrackingCalendar}
          className="w-full bg-gradient-to-r from-purple-600 to-pink-500 hover:from-purple-700 hover:to-pink-600 text-white py-6 text-lg"
          data-testid="download-protocol-btn"
        >
          <Download className="h-5 w-5 mr-2" />
          Download 12-Week Protocol PDF
        </Button>

        {/* Safety Reminder */}
        <div className="mt-4 p-3 bg-amber-50 rounded-lg border border-amber-200 text-center">
          <p className="text-sm text-amber-800">
            <strong>Important:</strong> SPF 30+ is mandatory daily. Apply protocol in PM routine only.
          </p>
        </div>
      </CardContent>
    </Card>
  );
};

export default ComboSuccessMessage;
