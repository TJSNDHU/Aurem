import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Beaker, Plus, Trash2, Edit, Save, X, AlertTriangle, Check, 
  RefreshCw, Tag, Calendar, Shield, Zap, Eye, ChevronDown, ChevronUp
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Priority labels
const PRIORITY_LABELS = {
  1: { label: 'Highest (SENSITIVE)', color: 'bg-red-100 text-red-700' },
  2: { label: 'High (ACID)', color: 'bg-orange-100 text-orange-700' },
  3: { label: 'Medium-High (ACNE)', color: 'bg-amber-100 text-amber-700' },
  4: { label: 'Medium (BRIGHTENER)', color: 'bg-yellow-100 text-yellow-700' },
  5: { label: 'Normal (PEPTIDE)', color: 'bg-green-100 text-green-700' },
  6: { label: 'Low (BARRIER)', color: 'bg-blue-100 text-blue-700' }
};

const ClinicalLogicManager = () => {
  const [milestones, setMilestones] = useState([]);
  const [availableTags, setAvailableTags] = useState([]);
  const [forbiddenWords, setForbiddenWords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingMilestone, setEditingMilestone] = useState(null);
  const [complianceWarning, setComplianceWarning] = useState(null);
  const [expandedMilestone, setExpandedMilestone] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    tags: [],
    phase_name: '',
    day_start: 1,
    day_end: 14,
    description: '',
    priority: 5,
    is_active: true
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = { Authorization: `Bearer ${token}` };
      
      const [milestonesRes, tagsRes] = await Promise.all([
        axios.get(`${API}/admin/clinical-logic/milestones`, { headers }),
        axios.get(`${API}/admin/clinical-logic/tags`, { headers })
      ]);
      
      setMilestones(milestonesRes.data?.milestones || []);
      setForbiddenWords(milestonesRes.data?.forbidden_words || []);
      setAvailableTags(tagsRes.data?.tags || []);
    } catch (err) {
      console.error('Failed to fetch data:', err);
      toast.error('Failed to load clinical logic data');
    } finally {
      setLoading(false);
    }
  };

  // Real-time compliance check
  const checkCompliance = async (text) => {
    if (!text) {
      setComplianceWarning(null);
      return;
    }
    
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.post(`${API}/admin/clinical-logic/validate-text`, 
        { text },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      if (!res.data.is_compliant) {
        setComplianceWarning({
          words: res.data.forbidden_words,
          suggestions: res.data.suggestions
        });
      } else {
        setComplianceWarning(null);
      }
    } catch (err) {
      console.error('Compliance check failed:', err);
    }
  };

  const handleDescriptionChange = (e) => {
    const text = e.target.value;
    setFormData({ ...formData, description: text });
    
    // Debounced compliance check
    clearTimeout(window._complianceTimeout);
    window._complianceTimeout = setTimeout(() => checkCompliance(text), 500);
  };

  const handleSave = async () => {
    if (!formData.phase_name || formData.tags.length === 0) {
      toast.error('Phase name and at least one tag required');
      return;
    }
    
    if (complianceWarning) {
      toast.error('Please fix compliance issues before saving');
      return;
    }
    
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = { Authorization: `Bearer ${token}` };
      
      if (editingMilestone) {
        const res = await axios.put(
          `${API}/admin/clinical-logic/milestones/${editingMilestone.id}`,
          formData,
          { headers }
        );
        
        if (res.data?.success === false) {
          toast.error(res.data.error || 'Failed to update');
          if (res.data.forbidden_words) {
            setComplianceWarning({
              words: res.data.forbidden_words,
              suggestions: res.data.suggestions
            });
          }
          return;
        }
        
        toast.success('Milestone updated!');
      } else {
        const res = await axios.post(
          `${API}/admin/clinical-logic/milestones`,
          formData,
          { headers }
        );
        
        if (res.data?.success === false) {
          toast.error(res.data.error || 'Failed to create');
          if (res.data.forbidden_words) {
            setComplianceWarning({
              words: res.data.forbidden_words,
              suggestions: res.data.suggestions
            });
          }
          return;
        }
        
        toast.success('Milestone created!');
      }
      
      setShowDialog(false);
      resetForm();
      fetchData();
    } catch (err) {
      console.error('Save failed:', err);
      toast.error(err.response?.data?.detail || 'Failed to save milestone');
    }
  };

  const handleEdit = (milestone) => {
    setEditingMilestone(milestone);
    setFormData({
      tags: milestone.tags || [],
      phase_name: milestone.phase_name || '',
      day_start: milestone.day_start || 1,
      day_end: milestone.day_end || 14,
      description: milestone.description || '',
      priority: milestone.priority || 5,
      is_active: milestone.is_active !== false
    });
    setComplianceWarning(null);
    setShowDialog(true);
  };

  const handleDelete = async (milestoneId) => {
    if (!window.confirm('Delete this milestone template?')) return;
    
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.delete(`${API}/admin/clinical-logic/milestones/${milestoneId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Milestone deleted');
      fetchData();
    } catch (err) {
      toast.error('Failed to delete milestone');
    }
  };

  const resetForm = () => {
    setEditingMilestone(null);
    setFormData({
      tags: [],
      phase_name: '',
      day_start: 1,
      day_end: 14,
      description: '',
      priority: 5,
      is_active: true
    });
    setComplianceWarning(null);
  };

  const toggleTag = (tagId) => {
    if (formData.tags.includes(tagId)) {
      setFormData({ ...formData, tags: formData.tags.filter(t => t !== tagId) });
    } else {
      setFormData({ ...formData, tags: [...formData.tags, tagId] });
    }
  };

  // Group milestones by tag for display
  const groupedMilestones = milestones.reduce((acc, m) => {
    const primaryTag = m.tags?.[0] || 'OTHER';
    if (!acc[primaryTag]) acc[primaryTag] = [];
    acc[primaryTag].push(m);
    return acc;
  }, {});

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Beaker className="h-6 w-6 text-purple-600" />
            Clinical Logic
          </h1>
          <p className="text-gray-500">Tag-based milestone templates for autonomous calendar generation</p>
        </div>
        <Button
          onClick={() => { resetForm(); setShowDialog(true); }}
          className="bg-gradient-to-r from-purple-600 to-pink-500"
          data-testid="create-milestone-btn"
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Milestone
        </Button>
      </div>

      {/* Compliance Notice */}
      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <Shield className="h-5 w-5 text-amber-600 mt-0.5" />
            <div>
              <h3 className="font-semibold text-amber-800">Canadian Cosmetic Compliance</h3>
              <p className="text-sm text-amber-700 mt-1">
                All milestone text is validated for cosmetic-only language. Forbidden words are automatically flagged.
              </p>
              <div className="flex flex-wrap gap-1 mt-2">
                {forbiddenWords.slice(0, 8).map(word => (
                  <Badge key={word} variant="outline" className="text-xs text-red-600 border-red-300">
                    {word}
                  </Badge>
                ))}
                {forbiddenWords.length > 8 && (
                  <Badge variant="outline" className="text-xs text-gray-500">
                    +{forbiddenWords.length - 8} more
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Available Tags Overview */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <Tag className="h-5 w-5 text-purple-600" />
            Product Tags Reference
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {availableTags.map(tag => (
              <Badge 
                key={tag.id}
                className={`
                  ${tag.category === 'Active' ? 'bg-purple-100 text-purple-700' : ''}
                  ${tag.category === 'Support' ? 'bg-blue-100 text-blue-700' : ''}
                  ${tag.category === 'Concern' ? 'bg-amber-100 text-amber-700' : ''}
                `}
              >
                {tag.label}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Milestone Templates */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
          <Calendar className="h-5 w-5 text-purple-600" />
          Milestone Templates ({milestones.length})
        </h2>
        
        {Object.entries(groupedMilestones).map(([tagName, tagMilestones]) => (
          <Card key={tagName} className="overflow-hidden">
            <div className="bg-gradient-to-r from-purple-600 to-pink-500 px-4 py-2">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <Tag className="h-4 w-4" />
                {tagName} ({tagMilestones.length})
              </h3>
            </div>
            <CardContent className="p-0">
              {tagMilestones.map(milestone => (
                <div 
                  key={milestone.id}
                  className={`border-b last:border-0 ${!milestone.is_active ? 'opacity-50' : ''}`}
                >
                  <div 
                    className="p-4 flex items-center justify-between cursor-pointer hover:bg-gray-50"
                    onClick={() => setExpandedMilestone(expandedMilestone === milestone.id ? null : milestone.id)}
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2">
                        {expandedMilestone === milestone.id ? (
                          <ChevronUp className="h-4 w-4 text-gray-400" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-gray-400" />
                        )}
                        <span className="font-medium">{milestone.phase_name}</span>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        Days {milestone.day_start}-{milestone.day_end}
                      </Badge>
                      <Badge className={PRIORITY_LABELS[milestone.priority]?.color || 'bg-gray-100'}>
                        P{milestone.priority}
                      </Badge>
                      {!milestone.is_active && (
                        <Badge variant="outline" className="text-gray-500">Inactive</Badge>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button 
                        size="sm" 
                        variant="ghost"
                        onClick={(e) => { e.stopPropagation(); handleEdit(milestone); }}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button 
                        size="sm" 
                        variant="ghost"
                        className="text-red-500"
                        onClick={(e) => { e.stopPropagation(); handleDelete(milestone.id); }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  
                  {/* Expanded content */}
                  {expandedMilestone === milestone.id && (
                    <div className="px-4 pb-4 bg-gray-50">
                      <p className="text-sm text-gray-700 mb-2">{milestone.description}</p>
                      <div className="flex flex-wrap gap-1">
                        {milestone.tags?.map(tag => (
                          <Badge key={tag} variant="outline" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
        
        {milestones.length === 0 && (
          <Card className="p-8 text-center">
            <Calendar className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-700">No milestone templates yet</h3>
            <p className="text-gray-500 mb-4">Create your first milestone to power the autonomous calendar</p>
            <Button onClick={() => setShowDialog(true)} variant="outline">
              <Plus className="h-4 w-4 mr-2" />
              Add First Milestone
            </Button>
          </Card>
        )}
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-purple-500" />
              {editingMilestone ? 'Edit Milestone Template' : 'Create Milestone Template'}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Tags Selection */}
            <div>
              <Label className="mb-2 block">Product Tags (triggers this milestone)</Label>
              <div className="flex flex-wrap gap-2 p-3 bg-gray-50 rounded-lg border">
                {availableTags.map(tag => (
                  <Badge 
                    key={tag.id}
                    className={`cursor-pointer transition-all ${
                      formData.tags.includes(tag.id)
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                    onClick={() => toggleTag(tag.id)}
                  >
                    {formData.tags.includes(tag.id) && <Check className="h-3 w-3 mr-1" />}
                    {tag.label}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Phase Name */}
            <div>
              <Label>Phase Name *</Label>
              <Input
                value={formData.phase_name}
                onChange={(e) => setFormData({ ...formData, phase_name: e.target.value })}
                placeholder="e.g., The Purge Window"
              />
            </div>

            {/* Day Range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Day Start</Label>
                <Input
                  type="number"
                  min="1"
                  max="90"
                  value={formData.day_start}
                  onChange={(e) => setFormData({ ...formData, day_start: parseInt(e.target.value) || 1 })}
                />
              </div>
              <div>
                <Label>Day End</Label>
                <Input
                  type="number"
                  min="1"
                  max="90"
                  value={formData.day_end}
                  onChange={(e) => setFormData({ ...formData, day_end: parseInt(e.target.value) || 14 })}
                />
              </div>
            </div>

            {/* Priority */}
            <div>
              <Label>Priority (lower = higher priority in conflicts)</Label>
              <Select
                value={String(formData.priority)}
                onValueChange={(value) => setFormData({ ...formData, priority: parseInt(value) })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(PRIORITY_LABELS).map(([val, info]) => (
                    <SelectItem key={val} value={val}>
                      P{val}: {info.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Description */}
            <div>
              <Label>Description (Canadian Compliant Language)</Label>
              <Textarea
                value={formData.description}
                onChange={handleDescriptionChange}
                placeholder="Describe this phase using cosmetic-approved language..."
                rows={4}
              />
              
              {/* Compliance Warning */}
              {complianceWarning && (
                <div className="mt-2 p-3 bg-red-50 rounded-lg border border-red-200">
                  <div className="flex items-center gap-2 text-red-700 mb-2">
                    <AlertTriangle className="h-4 w-4" />
                    <span className="font-semibold text-sm">Forbidden Words Detected</span>
                  </div>
                  <div className="space-y-1">
                    {complianceWarning.words.map(word => (
                      <div key={word} className="text-sm">
                        <span className="text-red-600 font-medium">"{word}"</span>
                        <span className="text-gray-600"> → Use: </span>
                        <span className="text-green-600 font-medium">"{complianceWarning.suggestions[word]}"</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Active Toggle */}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-2">
                <Eye className="h-4 w-4 text-gray-600" />
                <span className="font-medium">Active</span>
              </div>
              <button
                onClick={() => setFormData({ ...formData, is_active: !formData.is_active })}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  formData.is_active ? 'bg-green-500' : 'bg-gray-300'
                }`}
              >
                <span 
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    formData.is_active ? 'translate-x-6' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 mt-6 pt-4 border-t">
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleSave}
              disabled={!!complianceWarning}
              className="bg-gradient-to-r from-purple-600 to-pink-500"
            >
              <Save className="h-4 w-4 mr-2" />
              {editingMilestone ? 'Update Milestone' : 'Create Milestone'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ClinicalLogicManager;
