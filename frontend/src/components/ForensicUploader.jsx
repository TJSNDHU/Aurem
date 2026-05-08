/**
 * ORA Forensic Uploader
 * Floating "Help ORA Fix This" Button
 * 
 * Always accessible - drag/drop screenshots or paste error logs
 * ORA will analyze and provide genetic repairs
 */

import React, { useState, useRef } from 'react';
import { Upload, Bug, FileText, X, Loader, CheckCircle, AlertCircle } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const ForensicUploader = ({ token }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [mode, setMode] = useState('screenshot'); // 'screenshot' or 'text'
  const [errorText, setErrorText] = useState('');
  const [context, setContext] = useState('');
  
  const fileInputRef = useRef(null);

  const handleFileSelect = async (file) => {
    if (!file) return;
    
    // Validate file type
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      alert('Please upload PNG, JPEG, or WEBP images only');
      return;
    }
    
    setUploading(true);
    setResult(null);
    
    try {
      // Convert to base64
      const base64 = await fileToBase64(file);
      
      // Send to ORA
      const response = await fetch(`${API_URL}/api/forensic/analyze/screenshot`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          image_base64: base64.split(',')[1], // Remove data:image/... prefix
          context: context,
          user_description: 'User uploaded screenshot for analysis'
        })
      });
      
      const data = await response.json();
      setResult(data);
      
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Failed to analyze screenshot');
    } finally {
      setUploading(false);
    }
  };

  const handleTextAnalysis = async () => {
    if (!errorText.trim()) {
      alert('Please paste an error message');
      return;
    }
    
    setUploading(true);
    setResult(null);
    
    try {
      const response = await fetch(`${API_URL}/api/forensic/analyze/text`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          error_log: errorText,
          context: context
        })
      });
      
      const data = await response.json();
      setResult(data);
      
    } catch (error) {
      console.error('Analysis failed:', error);
      alert('Failed to analyze error log');
    } finally {
      setUploading(false);
    }
  };

  const handleRepair = async () => {
    if (!result || !result.analysis_id) return;
    
    setUploading(true);
    
    try {
      const response = await fetch(`${API_URL}/api/forensic/repair`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          analysis_id: result.analysis_id,
          auto_apply: false
        })
      });
      
      const data = await response.json();
      alert(data.message);
      
    } catch (error) {
      console.error('Repair failed:', error);
      alert('Failed to apply genetic repair');
    } finally {
      setUploading(false);
    }
  };

  const fileToBase64 = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result);
      reader.onerror = error => reject(error);
    });
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      handleFileSelect(files[0]);
    }
  };

  return (
    <>
      {/* Floating Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          style={{
            position: 'fixed',
            bottom: 100,
            right: 24,
            zIndex: 9998,
            width: 56,
            height: 56,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #FF6B6B 0%, #C92A2A 100%)',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 20px rgba(255, 107, 107, 0.4)',
            transition: 'all 0.3s'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'scale(1.1)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'scale(1)';
          }}
          title="Help ORA Fix This"
        >
          <Bug className="w-7 h-7 text-white" />
        </button>
      )}

      {/* Modal */}
      {isOpen && (
        <div style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          width: 420,
          maxHeight: '80vh',
          background: '#0A0A0A',
          border: '1px solid #1A1A1A',
          borderRadius: 16,
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.8)'
        }}>
          {/* Header */}
          <div style={{
            padding: 16,
            borderBottom: '1px solid #1A1A1A',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{display: 'flex', alignItems: 'center', gap: 10}}>
              <Bug className="w-5 h-5 text-[#FF6B6B]" />
              <div>
                <h3 style={{fontSize: 14, fontWeight: 600, color: '#F4F4F4'}}>
                  ORA Forensic Suite
                </h3>
                <p style={{fontSize: 11, color: '#666'}}>
                  AI-Powered Root Cause Analysis
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                setIsOpen(false);
                setResult(null);
              }}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#888',
                padding: 4
              }}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Mode Selector */}
          <div style={{
            padding: 12,
            display: 'flex',
            gap: 8,
            borderBottom: '1px solid #1A1A1A'
          }}>
            <button
              onClick={() => setMode('screenshot')}
              style={{
                flex: 1,
                padding: '8px 12px',
                background: mode === 'screenshot' ? '#1A3A1A' : '#0A0A0A',
                border: `1px solid ${mode === 'screenshot' ? '#2A5A2A' : '#1A1A1A'}`,
                borderRadius: 8,
                color: mode === 'screenshot' ? '#4A4' : '#888',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                justifyContent: 'center'
              }}
            >
              <Upload className="w-4 h-4" />
              Screenshot
            </button>
            <button
              onClick={() => setMode('text')}
              style={{
                flex: 1,
                padding: '8px 12px',
                background: mode === 'text' ? '#1A3A1A' : '#0A0A0A',
                border: `1px solid ${mode === 'text' ? '#2A5A2A' : '#1A1A1A'}`,
                borderRadius: 8,
                color: mode === 'text' ? '#4A4' : '#888',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                justifyContent: 'center'
              }}
            >
              <FileText className="w-4 h-4" />
              Error Log
            </button>
          </div>

          {/* Content */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: 16
          }}>
            {/* Context Input */}
            <div style={{marginBottom: 12}}>
              <label style={{fontSize: 11, color: '#888', marginBottom: 6, display: 'block'}}>
                Context (optional)
              </label>
              <input
                type="text"
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="e.g., 'login flow', 'checkout page'"
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  background: '#050505',
                  border: '1px solid #1A1A1A',
                  borderRadius: 8,
                  color: '#F4F4F4',
                  fontSize: 12,
                  outline: 'none'
                }}
              />
            </div>

            {mode === 'screenshot' ? (
              // Screenshot Upload
              <div
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                style={{
                  border: '2px dashed #1A1A1A',
                  borderRadius: 12,
                  padding: 24,
                  textAlign: 'center',
                  cursor: 'pointer',
                  background: '#050505'
                }}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="w-8 h-8 mx-auto mb-3 text-[#666]" />
                <p style={{fontSize: 13, color: '#AAA', marginBottom: 4}}>
                  Drag & drop screenshot here
                </p>
                <p style={{fontSize: 11, color: '#666'}}>
                  or click to browse
                </p>
                <p style={{fontSize: 10, color: '#555', marginTop: 8}}>
                  PNG, JPEG, WEBP only
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => e.target.files && handleFileSelect(e.target.files[0])}
                  style={{display: 'none'}}
                />
              </div>
            ) : (
              // Text Error Log
              <div>
                <textarea
                  value={errorText}
                  onChange={(e) => setErrorText(e.target.value)}
                  placeholder="Paste error message or stack trace here..."
                  style={{
                    width: '100%',
                    height: 150,
                    padding: 12,
                    background: '#050505',
                    border: '1px solid #1A1A1A',
                    borderRadius: 8,
                    color: '#F4F4F4',
                    fontSize: 11,
                    fontFamily: 'monospace',
                    resize: 'none',
                    outline: 'none'
                  }}
                />
                <button
                  onClick={handleTextAnalysis}
                  disabled={uploading || !errorText.trim()}
                  style={{
                    width: '100%',
                    marginTop: 12,
                    padding: '10px 16px',
                    background: uploading ? '#333' : 'linear-gradient(135deg, #FF6B6B 0%, #C92A2A 100%)',
                    border: 'none',
                    borderRadius: 8,
                    color: '#FFF',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: uploading ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8
                  }}
                >
                  {uploading ? (
                    <>
                      <Loader className="w-4 h-4 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <Bug className="w-4 h-4" />
                      Analyze Error
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Results */}
            {result && (
              <div style={{marginTop: 16, padding: 12, background: '#050505', border: '1px solid #1A1A1A', borderRadius: 8}}>
                <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8}}>
                  {result.analysis?.confidence_score > 0.7 ? (
                    <CheckCircle className="w-4 h-4 text-[#4A4]" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-[#FA4]" />
                  )}
                  <span style={{fontSize: 12, fontWeight: 600, color: '#F4F4F4'}}>
                    Analysis Complete
                  </span>
                  <span style={{fontSize: 11, color: '#888'}}>
                    ({Math.round(result.analysis?.confidence_score * 100)}% confidence)
                  </span>
                </div>

                <div style={{fontSize: 11, color: '#AAA', marginBottom: 8}}>
                  <strong style={{color: '#F4F4F4'}}>Error Type:</strong> {result.analysis?.detected_error_type}
                </div>

                <div style={{fontSize: 11, color: '#AAA', marginBottom: 12}}>
                  <strong style={{color: '#F4F4F4'}}>Root Cause:</strong><br />
                  {result.analysis?.root_cause_hypothesis}
                </div>

                {result.code_trace?.found && (
                  <button
                    onClick={handleRepair}
                    disabled={uploading}
                    style={{
                      width: '100%',
                      padding: '10px 16px',
                      background: 'linear-gradient(135deg, #4A4 0%, #2A2 100%)',
                      border: 'none',
                      borderRadius: 8,
                      color: '#FFF',
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    Apply Genetic Repair
                  </button>
                )}
              </div>
            )}

            {uploading && mode === 'screenshot' && (
              <div style={{marginTop: 16, textAlign: 'center'}}>
                <Loader className="w-8 h-8 mx-auto mb-3 animate-spin text-[#FF6B6B]" />
                <p style={{fontSize: 12, color: '#888'}}>
                  ORA is analyzing your screenshot...
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default ForensicUploader;
