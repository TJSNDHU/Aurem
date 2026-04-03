/**
 * ReRoots AI PWA Progress Tab
 * Encrypted Skin Photo Vault with Camera Integration
 */

import React, { useState, useRef, useCallback } from 'react';
import { Camera, Image, Trash2, Download, Calendar, Tag, ChevronDown, Loader2, X, Check, Shield, Plus, ZoomIn } from 'lucide-react';
import { useVault } from './VaultProvider';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

// Skin zones for categorization
const SKIN_ZONES = [
  { id: 'face', label: 'Face', icon: '😊' },
  { id: 'forehead', label: 'Forehead', icon: '🔼' },
  { id: 'cheeks', label: 'Cheeks', icon: '🔵' },
  { id: 'chin', label: 'Chin', icon: '🔽' },
  { id: 'neck', label: 'Neck', icon: '📿' },
  { id: 'other', label: 'Other', icon: '📍' }
];

// Photo categories
const CATEGORIES = [
  { id: 'progress', label: 'Progress', color: 'amber' },
  { id: 'concern', label: 'Concern', color: 'red' },
  { id: 'before', label: 'Before', color: 'blue' },
  { id: 'after', label: 'After', color: 'green' }
];

export function PWAProgress() {
  const { 
    isUnlocked, 
    photos, 
    savePhoto, 
    loadPhoto, 
    deletePhoto, 
    storageUsed,
    formatStorageSize 
  } = useVault();
  
  const [showCamera, setShowCamera] = useState(false);
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [loadedPhotoUrl, setLoadedPhotoUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [filter, setFilter] = useState('all');

  // View a photo
  const handleViewPhoto = async (photo) => {
    setIsLoading(true);
    try {
      const result = await loadPhoto(photo.id);
      setLoadedPhotoUrl(result.url);
      setSelectedPhoto(result.metadata);
    } catch (error) {
      toast.error('Failed to decrypt photo');
    } finally {
      setIsLoading(false);
    }
  };

  // Delete a photo
  const handleDeletePhoto = async (photoId) => {
    if (!confirm('Delete this photo? This cannot be undone.')) return;
    
    try {
      await deletePhoto(photoId);
      setSelectedPhoto(null);
      setLoadedPhotoUrl(null);
      toast.success('Photo deleted');
    } catch (error) {
      toast.error('Failed to delete photo');
    }
  };

  // Close photo viewer and revoke URL
  const closeViewer = () => {
    if (loadedPhotoUrl) {
      URL.revokeObjectURL(loadedPhotoUrl);
    }
    setSelectedPhoto(null);
    setLoadedPhotoUrl(null);
  };

  // Filtered photos
  const filteredPhotos = filter === 'all' 
    ? photos 
    : photos.filter(p => p.category === filter || p.skinZone === filter);

  return (
    <div className="pb-28 px-4">
      {/* Header */}
      <div className="pt-4 pb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">Skin Progress</h2>
            <p className="text-white/60 text-sm mt-1">
              {photos.length} photos • {formatStorageSize(storageUsed)}
            </p>
          </div>
          
          <button
            onClick={() => setShowCamera(true)}
            className="w-12 h-12 rounded-full bg-gradient-to-r from-amber-500 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/30"
          >
            <Plus className="w-6 h-6 text-black" />
          </button>
        </div>

        {/* Security Badge */}
        <div className="mt-4 flex items-center gap-2 text-xs text-white/40">
          <Shield className="w-4 h-4" />
          <span>AES-256 Encrypted • Stored on device only</span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-2 -mx-4 px-4 scrollbar-hide">
        <button
          onClick={() => setFilter('all')}
          className={`px-4 py-2 rounded-full whitespace-nowrap text-sm font-medium transition-all ${
            filter === 'all'
              ? 'bg-amber-500 text-black'
              : 'bg-white/10 text-white/80'
          }`}
        >
          All
        </button>
        {CATEGORIES.map(cat => (
          <button
            key={cat.id}
            onClick={() => setFilter(cat.id)}
            className={`px-4 py-2 rounded-full whitespace-nowrap text-sm font-medium transition-all ${
              filter === cat.id
                ? 'bg-amber-500 text-black'
                : 'bg-white/10 text-white/80'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Photos Grid */}
      {filteredPhotos.length > 0 ? (
        <div className="grid grid-cols-3 gap-2">
          {filteredPhotos.map(photo => (
            <button
              key={photo.id}
              onClick={() => handleViewPhoto(photo)}
              className="aspect-square rounded-xl bg-white/10 border border-white/10 relative overflow-hidden group"
            >
              {/* Placeholder with category color */}
              <div className={`absolute inset-0 bg-gradient-to-br ${
                photo.category === 'progress' ? 'from-amber-500/20 to-amber-600/20' :
                photo.category === 'concern' ? 'from-red-500/20 to-red-600/20' :
                photo.category === 'before' ? 'from-blue-500/20 to-blue-600/20' :
                'from-green-500/20 to-green-600/20'
              }`} />
              
              {/* Lock icon (encrypted) */}
              <div className="absolute inset-0 flex items-center justify-center">
                <Shield className="w-8 h-8 text-white/20" />
              </div>
              
              {/* Category badge */}
              <div className="absolute top-1 left-1">
                <span className={`px-1.5 py-0.5 rounded text-[8px] font-semibold ${
                  photo.category === 'progress' ? 'bg-amber-500/80 text-black' :
                  photo.category === 'concern' ? 'bg-red-500/80 text-white' :
                  photo.category === 'before' ? 'bg-blue-500/80 text-white' :
                  'bg-green-500/80 text-white'
                }`}>
                  {photo.category?.toUpperCase()}
                </span>
              </div>
              
              {/* Date */}
              <div className="absolute bottom-1 right-1 text-[8px] text-white/40">
                {new Date(photo.timestamp).toLocaleDateString()}
              </div>

              {/* Hover overlay */}
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <ZoomIn className="w-6 h-6 text-white" />
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="text-center py-16">
          <Camera className="w-16 h-16 text-white/20 mx-auto mb-4" />
          <h3 className="text-white font-semibold mb-2">No photos yet</h3>
          <p className="text-white/60 text-sm mb-6">
            Start tracking your skin journey with encrypted photos
          </p>
          <Button
            onClick={() => setShowCamera(true)}
            className="bg-gradient-to-r from-amber-500 to-amber-600 text-black"
          >
            <Camera className="w-4 h-4 mr-2" />
            Take First Photo
          </Button>
        </div>
      )}

      {/* Camera Modal */}
      {showCamera && (
        <CameraCapture 
          onCapture={async (photoData, metadata) => {
            try {
              await savePhoto(photoData, metadata);
              toast.success('Photo saved to vault');
              setShowCamera(false);
            } catch (error) {
              toast.error('Failed to save photo');
            }
          }}
          onClose={() => setShowCamera(false)}
        />
      )}

      {/* Photo Viewer Modal */}
      {selectedPhoto && (
        <PhotoViewer
          photo={selectedPhoto}
          photoUrl={loadedPhotoUrl}
          isLoading={isLoading}
          onClose={closeViewer}
          onDelete={() => handleDeletePhoto(selectedPhoto.id)}
        />
      )}
    </div>
  );
}

/**
 * Camera Capture Component
 */
function CameraCapture({ onCapture, onClose }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [stream, setStream] = useState(null);
  const [capturedImage, setCapturedImage] = useState(null);
  const [category, setCategory] = useState('progress');
  const [skinZone, setSkinZone] = useState('face');
  const [label, setLabel] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [facingMode, setFacingMode] = useState('user');

  // Start camera
  const startCamera = useCallback(async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: facingMode,
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        }
      });
      
      setStream(mediaStream);
      
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch (error) {
      console.error('[Camera] Error:', error);
      toast.error('Camera access denied');
    }
  }, [facingMode]);

  // Stop camera
  const stopCamera = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
  }, [stream]);

  // Initialize camera on mount
  React.useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, [facingMode]);

  // Capture photo
  const capture = () => {
    if (!videoRef.current || !canvasRef.current) return;
    
    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    const ctx = canvas.getContext('2d');
    
    // Flip for selfie camera
    if (facingMode === 'user') {
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    
    ctx.drawImage(video, 0, 0);
    
    canvas.toBlob((blob) => {
      setCapturedImage(blob);
      stopCamera();
    }, 'image/jpeg', 0.9);
  };

  // Switch camera
  const switchCamera = () => {
    stopCamera();
    setFacingMode(prev => prev === 'user' ? 'environment' : 'user');
  };

  // Retake photo
  const retake = () => {
    setCapturedImage(null);
    startCamera();
  };

  // Save photo
  const save = async () => {
    if (!capturedImage) return;
    
    setIsSaving(true);
    try {
      const arrayBuffer = await capturedImage.arrayBuffer();
      await onCapture(arrayBuffer, {
        category,
        skinZone,
        label,
        mimeType: 'image/jpeg'
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black">
      {/* Close button */}
      <button
        onClick={() => {
          stopCamera();
          onClose();
        }}
        className="absolute top-4 right-4 z-10 w-10 h-10 rounded-full bg-white/10 flex items-center justify-center"
      >
        <X className="w-6 h-6 text-white" />
      </button>

      {/* Camera/Preview */}
      <div className="h-2/3 relative bg-black">
        {capturedImage ? (
          <img 
            src={URL.createObjectURL(capturedImage)}
            alt="Captured"
            className="w-full h-full object-cover"
          />
        ) : (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className={`w-full h-full object-cover ${facingMode === 'user' ? 'scale-x-[-1]' : ''}`}
          />
        )}
        
        {/* Hidden canvas for capture */}
        <canvas ref={canvasRef} className="hidden" />

        {/* Camera guides */}
        {!capturedImage && (
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute inset-12 border-2 border-white/30 rounded-3xl" />
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-4 h-4 border-2 border-white/50 rounded-full" />
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="h-1/3 bg-[#0a0a0f] px-4 py-6">
        {capturedImage ? (
          // Post-capture options
          <div className="space-y-4">
            {/* Category Selection */}
            <div>
              <label className="text-white/60 text-xs mb-2 block">Category</label>
              <div className="flex gap-2">
                {CATEGORIES.map(cat => (
                  <button
                    key={cat.id}
                    onClick={() => setCategory(cat.id)}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                      category === cat.id
                        ? 'bg-amber-500 text-black'
                        : 'bg-white/10 text-white/80'
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Skin Zone */}
            <div>
              <label className="text-white/60 text-xs mb-2 block">Skin Zone</label>
              <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                {SKIN_ZONES.map(zone => (
                  <button
                    key={zone.id}
                    onClick={() => setSkinZone(zone.id)}
                    className={`px-3 py-2 rounded-lg text-sm whitespace-nowrap transition-all ${
                      skinZone === zone.id
                        ? 'bg-white/20 text-white'
                        : 'bg-white/5 text-white/60'
                    }`}
                  >
                    {zone.icon} {zone.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex gap-3 pt-2">
              <Button
                onClick={retake}
                variant="outline"
                className="flex-1 h-12 border-white/20 text-white"
              >
                Retake
              </Button>
              <Button
                onClick={save}
                disabled={isSaving}
                className="flex-1 h-12 bg-gradient-to-r from-amber-500 to-amber-600 text-black font-semibold"
              >
                {isSaving ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <Check className="w-5 h-5 mr-2" />
                    Save to Vault
                  </>
                )}
              </Button>
            </div>
          </div>
        ) : (
          // Camera controls
          <div className="flex items-center justify-around h-full">
            {/* Gallery button */}
            <button className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center">
              <Image className="w-6 h-6 text-white" />
            </button>

            {/* Capture button */}
            <button
              onClick={capture}
              className="w-20 h-20 rounded-full bg-white border-4 border-amber-500 flex items-center justify-center"
            >
              <div className="w-16 h-16 rounded-full bg-white" />
            </button>

            {/* Switch camera */}
            <button 
              onClick={switchCamera}
              className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center"
            >
              <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M16 3h5v5M8 21H3v-5M21 3l-7 7M3 21l7-7" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Photo Viewer Component
 */
function PhotoViewer({ photo, photoUrl, isLoading, onClose, onDelete }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/95">
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-10 p-4 flex items-center justify-between bg-gradient-to-b from-black/80 to-transparent">
        <button
          onClick={onClose}
          className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center"
        >
          <X className="w-6 h-6 text-white" />
        </button>
        
        <div className="flex gap-2">
          <button
            onClick={onDelete}
            className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center"
          >
            <Trash2 className="w-5 h-5 text-red-400" />
          </button>
        </div>
      </div>

      {/* Photo */}
      <div className="h-full flex items-center justify-center p-4">
        {isLoading ? (
          <Loader2 className="w-12 h-12 text-amber-500 animate-spin" />
        ) : photoUrl ? (
          <img 
            src={photoUrl}
            alt="Progress photo"
            className="max-w-full max-h-full object-contain rounded-lg"
          />
        ) : (
          <div className="text-white/60">Failed to load photo</div>
        )}
      </div>

      {/* Info footer */}
      <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent">
        <div className="flex items-center gap-4">
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${
            photo.category === 'progress' ? 'bg-amber-500/80 text-black' :
            photo.category === 'concern' ? 'bg-red-500/80 text-white' :
            photo.category === 'before' ? 'bg-blue-500/80 text-white' :
            'bg-green-500/80 text-white'
          }`}>
            {photo.category}
          </div>
          
          <span className="text-white/60 text-sm">
            {SKIN_ZONES.find(z => z.id === photo.skinZone)?.icon} {photo.skinZone}
          </span>
          
          <span className="text-white/60 text-sm ml-auto">
            {new Date(photo.timestamp).toLocaleDateString()}
          </span>
        </div>
      </div>
    </div>
  );
}

export default PWAProgress;
