import React, { useState, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// API URL configuration
const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // For localhost development
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    
    // For custom domains (reroots.ca, etc.) - ALWAYS use same origin
    if (!hostname.includes('preview.emergentagent.com') && !hostname.includes('emergent.host')) {
      return window.location.origin;
    }
    
    // For preview/staging environments, use env var if available
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }
    
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};

const BACKEND_URL = getBackendUrl();
const API = `${BACKEND_URL}/api`;

export const ImageUploader = ({ value, onChange, placeholder = "Enter image URL or upload", showWarning = false, acceptVideo = false }) => {
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');
    
    if (!isImage && !isVideo) {
      toast.error("Please select an image or video file");
      return;
    }
    
    if (isVideo && !acceptVideo) {
      toast.error("Please select an image file");
      return;
    }

    // Validate file size (max 10MB for images, 100MB for videos)
    const maxSize = isVideo ? 100 * 1024 * 1024 : 10 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error(isVideo ? "Video must be less than 100MB" : "Image must be less than 10MB");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const endpoint = isVideo ? `${API}/upload/video` : `${API}/upload/image`;
      const res = await axios.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000 // 2 minutes for larger files
      });
      
      const mediaUrl = res.data.url;
      const isPermanent = res.data.permanent;
      const host = res.data.host;
      
      // Use the URL directly if it's already a full URL
      const finalUrl = mediaUrl.startsWith('http') ? mediaUrl : `${BACKEND_URL}${mediaUrl}`;
      onChange(finalUrl);
      
      // Clear the input so the same file can be selected again
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      
      if (isPermanent) {
        const hostName = host === 'catbox' ? 'Catbox' : host === 'imgbb' ? 'ImgBB' : host;
        toast.success(`${isVideo ? 'Video' : 'Image'} uploaded to ${hostName} - Permanent! ✓`);
      } else {
        toast.success(`${isVideo ? 'Video' : 'Image'} uploaded!`);
        if (showWarning) {
          toast.warning("Local upload - may not persist after deployment", { duration: 5000 });
        }
      }
    } catch (error) {
      console.error("Upload error:", error);
      toast.error(`Failed to upload ${isVideo ? 'video' : 'image'}: ${error.message || 'Unknown error'}`);
    }
    setUploading(false);
  };

  const acceptTypes = acceptVideo ? "image/*,video/*" : "image/*";

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="flex-1"
        />
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          accept={acceptTypes}
          className="hidden"
        />
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          title={acceptVideo ? "Upload image or video" : "Upload image (auto-saved permanently)"}
        >
          {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
        </Button>
      </div>
      {value && (
        <div className="relative w-20 h-20 rounded border overflow-hidden">
          <img src={value} alt="Preview" className="w-full h-full object-cover" />
          <button
            type="button"
            onClick={() => onChange("")}
            className="absolute top-0 right-0 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
};

export default ImageUploader;
