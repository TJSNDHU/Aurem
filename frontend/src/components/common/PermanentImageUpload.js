import React, { useState, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { API, BACKEND_URL } from '@/lib/api';

// PermanentImageUpload - Uses free permanent hosting (Catbox, ImgBB, or 0x0.st)
const PermanentImageUpload = ({ onUpload }) => {
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      toast.error("Please select an image file");
      return;
    }

    // Validate file size (max 10MB for catbox)
    if (file.size > 10 * 1024 * 1024) {
      toast.error("Image must be less than 10MB");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post(`${API}/upload/image`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000 // 60 second timeout for upload
      });
      
      const imageUrl = res.data.url;
      const host = res.data.host;
      const isPermanent = res.data.permanent;
      
      if (imageUrl && isPermanent) {
        onUpload(imageUrl);
        const hostName = host === 'catbox' ? 'Catbox' : host === 'imgbb' ? 'ImgBB' : host;
        toast.success(`Image uploaded to ${hostName} - Permanent! ✓`);
      } else if (imageUrl) {
        // Fallback: use the returned URL
        const fullUrl = imageUrl.startsWith('http') ? imageUrl : `${BACKEND_URL}${imageUrl}`;
        onUpload(fullUrl);
        toast.warning("Image saved locally - may not persist after deployment");
      } else {
        throw new Error("No URL returned");
      }
    } catch (error) {
      console.error("Upload error:", error);
      toast.error("Failed to upload image. Try using an external URL instead.");
    }
    setUploading(false);
    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="flex items-center gap-2">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        accept="image/*"
        className="hidden"
      />
      <Button
        type="button"
        variant="outline"
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        className="border-green-300 hover:border-green-500 hover:bg-green-50"
      >
        {uploading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            Uploading...
          </>
        ) : (
          <>
            <Upload className="h-4 w-4 mr-2" />
            Upload Image (Permanent)
          </>
        )}
      </Button>
      <span className="text-xs text-green-600">✓ Auto-saved permanently</span>
    </div>
  );
};

export default PermanentImageUpload;
