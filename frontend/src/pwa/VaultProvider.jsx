/**
 * ReRoots AI Encrypted Vault Provider
 * IndexedDB + AES-256-GCM Client-Side Encryption
 * For secure storage of high-res skin photos
 * 
 * SECURITY: Photos never leave the device unencrypted
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

const VaultContext = createContext(null);

// IndexedDB Configuration
const DB_NAME = 'reroots-vault';
const DB_VERSION = 1;
const STORE_NAME = 'encrypted-photos';
const KEY_STORE = 'encryption-keys';

// AES-256-GCM Configuration
const ALGORITHM = 'AES-GCM';
const KEY_LENGTH = 256;
const IV_LENGTH = 12; // 96 bits for GCM

/**
 * VaultProvider - Manages encrypted photo storage
 * Uses Web Crypto API for AES-256-GCM encryption
 */
export function VaultProvider({ children }) {
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [photos, setPhotos] = useState([]);
  const [error, setError] = useState(null);
  const [storageUsed, setStorageUsed] = useState(0);
  
  const dbRef = useRef(null);
  const cryptoKeyRef = useRef(null);

  // Initialize IndexedDB
  const initDB = useCallback(() => {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      
      request.onerror = () => {
        console.error('[Vault] IndexedDB error:', request.error);
        reject(request.error);
      };
      
      request.onsuccess = () => {
        dbRef.current = request.result;
        console.log('[Vault] IndexedDB initialized');
        resolve(request.result);
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Store for encrypted photos
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const photoStore = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
          photoStore.createIndex('timestamp', 'timestamp', { unique: false });
          photoStore.createIndex('category', 'category', { unique: false });
          console.log('[Vault] Created encrypted-photos store');
        }
        
        // Store for encryption keys (wrapped with user passphrase)
        if (!db.objectStoreNames.contains(KEY_STORE)) {
          db.createObjectStore(KEY_STORE, { keyPath: 'id' });
          console.log('[Vault] Created encryption-keys store');
        }
      };
    });
  }, []);

  // Generate a new AES-256 key
  const generateKey = useCallback(async () => {
    const key = await crypto.subtle.generateKey(
      { name: ALGORITHM, length: KEY_LENGTH },
      true, // extractable for backup
      ['encrypt', 'decrypt']
    );
    return key;
  }, []);

  // Derive key from user passphrase (for key wrapping)
  const deriveKeyFromPassphrase = useCallback(async (passphrase, salt) => {
    const encoder = new TextEncoder();
    const keyMaterial = await crypto.subtle.importKey(
      'raw',
      encoder.encode(passphrase),
      'PBKDF2',
      false,
      ['deriveKey']
    );
    
    const derivedKey = await crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt: salt,
        iterations: 100000,
        hash: 'SHA-256'
      },
      keyMaterial,
      { name: ALGORITHM, length: KEY_LENGTH },
      false,
      ['wrapKey', 'unwrapKey']
    );
    
    return derivedKey;
  }, []);

  // Wrap (encrypt) the vault key with user's passphrase
  const wrapVaultKey = useCallback(async (vaultKey, passphrase) => {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const wrappingKey = await deriveKeyFromPassphrase(passphrase, salt);
    const iv = crypto.getRandomValues(new Uint8Array(IV_LENGTH));
    
    const wrappedKey = await crypto.subtle.wrapKey(
      'raw',
      vaultKey,
      wrappingKey,
      { name: ALGORITHM, iv: iv }
    );
    
    return {
      wrappedKey: new Uint8Array(wrappedKey),
      salt: salt,
      iv: iv
    };
  }, [deriveKeyFromPassphrase]);

  // Unwrap (decrypt) the vault key with user's passphrase
  const unwrapVaultKey = useCallback(async (wrappedData, passphrase) => {
    const wrappingKey = await deriveKeyFromPassphrase(passphrase, wrappedData.salt);
    
    const vaultKey = await crypto.subtle.unwrapKey(
      'raw',
      wrappedData.wrappedKey,
      wrappingKey,
      { name: ALGORITHM, iv: wrappedData.iv },
      { name: ALGORITHM, length: KEY_LENGTH },
      true,
      ['encrypt', 'decrypt']
    );
    
    return vaultKey;
  }, [deriveKeyFromPassphrase]);

  // Store wrapped key in IndexedDB
  const storeWrappedKey = useCallback(async (wrappedData) => {
    return new Promise((resolve, reject) => {
      const tx = dbRef.current.transaction(KEY_STORE, 'readwrite');
      const store = tx.objectStore(KEY_STORE);
      
      const request = store.put({
        id: 'vault-key',
        wrappedKey: Array.from(wrappedData.wrappedKey),
        salt: Array.from(wrappedData.salt),
        iv: Array.from(wrappedData.iv),
        createdAt: Date.now()
      });
      
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }, []);

  // Retrieve wrapped key from IndexedDB
  const getWrappedKey = useCallback(async () => {
    return new Promise((resolve, reject) => {
      const tx = dbRef.current.transaction(KEY_STORE, 'readonly');
      const store = tx.objectStore(KEY_STORE);
      const request = store.get('vault-key');
      
      request.onsuccess = () => {
        if (request.result) {
          resolve({
            wrappedKey: new Uint8Array(request.result.wrappedKey),
            salt: new Uint8Array(request.result.salt),
            iv: new Uint8Array(request.result.iv)
          });
        } else {
          resolve(null);
        }
      };
      request.onerror = () => reject(request.error);
    });
  }, []);

  // Encrypt data with vault key
  const encryptData = useCallback(async (data) => {
    if (!cryptoKeyRef.current) {
      throw new Error('Vault is locked');
    }
    
    const iv = crypto.getRandomValues(new Uint8Array(IV_LENGTH));
    const encodedData = typeof data === 'string' 
      ? new TextEncoder().encode(data)
      : new Uint8Array(data);
    
    const encryptedBuffer = await crypto.subtle.encrypt(
      { name: ALGORITHM, iv: iv },
      cryptoKeyRef.current,
      encodedData
    );
    
    return {
      encrypted: new Uint8Array(encryptedBuffer),
      iv: iv
    };
  }, []);

  // Decrypt data with vault key
  const decryptData = useCallback(async (encryptedData, iv) => {
    if (!cryptoKeyRef.current) {
      throw new Error('Vault is locked');
    }
    
    const decryptedBuffer = await crypto.subtle.decrypt(
      { name: ALGORITHM, iv: iv },
      cryptoKeyRef.current,
      encryptedData
    );
    
    return new Uint8Array(decryptedBuffer);
  }, []);

  // Initialize or create vault
  const initializeVault = useCallback(async (passphrase) => {
    try {
      await initDB();
      
      const existingKey = await getWrappedKey();
      
      if (existingKey) {
        // Unlock existing vault
        cryptoKeyRef.current = await unwrapVaultKey(existingKey, passphrase);
        console.log('[Vault] Existing vault unlocked');
      } else {
        // Create new vault
        const newKey = await generateKey();
        const wrappedData = await wrapVaultKey(newKey, passphrase);
        await storeWrappedKey(wrappedData);
        cryptoKeyRef.current = newKey;
        console.log('[Vault] New vault created');
      }
      
      setIsUnlocked(true);
      setIsInitialized(true);
      await loadPhotos();
      
      return true;
    } catch (err) {
      console.error('[Vault] Initialization error:', err);
      setError(err.message);
      return false;
    }
  }, [initDB, getWrappedKey, unwrapVaultKey, generateKey, wrapVaultKey, storeWrappedKey]);

  // Lock the vault
  const lockVault = useCallback(() => {
    cryptoKeyRef.current = null;
    setIsUnlocked(false);
    setPhotos([]);
    console.log('[Vault] Vault locked');
  }, []);

  // Save encrypted photo
  const savePhoto = useCallback(async (photoData, metadata = {}) => {
    if (!isUnlocked) {
      throw new Error('Vault is locked');
    }
    
    try {
      const { encrypted, iv } = await encryptData(photoData);
      
      const photoRecord = {
        id: `photo_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        encryptedData: Array.from(encrypted),
        iv: Array.from(iv),
        timestamp: Date.now(),
        category: metadata.category || 'progress',
        label: metadata.label || '',
        skinZone: metadata.skinZone || 'face',
        size: photoData.length || photoData.byteLength,
        mimeType: metadata.mimeType || 'image/jpeg'
      };
      
      return new Promise((resolve, reject) => {
        const tx = dbRef.current.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const request = store.put(photoRecord);
        
        request.onsuccess = async () => {
          console.log('[Vault] Photo saved:', photoRecord.id);
          await loadPhotos();
          resolve(photoRecord.id);
        };
        request.onerror = () => reject(request.error);
      });
    } catch (err) {
      console.error('[Vault] Save photo error:', err);
      throw err;
    }
  }, [isUnlocked, encryptData]);

  // Load and decrypt photo
  const loadPhoto = useCallback(async (photoId) => {
    if (!isUnlocked) {
      throw new Error('Vault is locked');
    }
    
    return new Promise(async (resolve, reject) => {
      const tx = dbRef.current.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const request = store.get(photoId);
      
      request.onsuccess = async () => {
        if (!request.result) {
          reject(new Error('Photo not found'));
          return;
        }
        
        try {
          const decrypted = await decryptData(
            new Uint8Array(request.result.encryptedData),
            new Uint8Array(request.result.iv)
          );
          
          const blob = new Blob([decrypted], { type: request.result.mimeType });
          const url = URL.createObjectURL(blob);
          
          resolve({
            url,
            metadata: {
              id: request.result.id,
              timestamp: request.result.timestamp,
              category: request.result.category,
              label: request.result.label,
              skinZone: request.result.skinZone,
              size: request.result.size
            }
          });
        } catch (err) {
          reject(err);
        }
      };
      request.onerror = () => reject(request.error);
    });
  }, [isUnlocked, decryptData]);

  // Load photo metadata (without decryption)
  const loadPhotos = useCallback(async () => {
    if (!dbRef.current) return;
    
    return new Promise((resolve, reject) => {
      const tx = dbRef.current.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const request = store.getAll();
      
      request.onsuccess = () => {
        const photoMeta = request.result.map(p => ({
          id: p.id,
          timestamp: p.timestamp,
          category: p.category,
          label: p.label,
          skinZone: p.skinZone,
          size: p.size
        }));
        
        // Calculate storage used
        const totalSize = request.result.reduce((sum, p) => sum + (p.encryptedData?.length || 0), 0);
        setStorageUsed(totalSize);
        
        setPhotos(photoMeta.sort((a, b) => b.timestamp - a.timestamp));
        resolve(photoMeta);
      };
      request.onerror = () => reject(request.error);
    });
  }, []);

  // Delete photo
  const deletePhoto = useCallback(async (photoId) => {
    if (!isUnlocked) {
      throw new Error('Vault is locked');
    }
    
    return new Promise((resolve, reject) => {
      const tx = dbRef.current.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const request = store.delete(photoId);
      
      request.onsuccess = async () => {
        console.log('[Vault] Photo deleted:', photoId);
        await loadPhotos();
        resolve();
      };
      request.onerror = () => reject(request.error);
    });
  }, [isUnlocked, loadPhotos]);

  // Export vault (encrypted backup)
  const exportVault = useCallback(async () => {
    if (!isUnlocked) {
      throw new Error('Vault is locked');
    }
    
    return new Promise((resolve, reject) => {
      const tx = dbRef.current.transaction([STORE_NAME, KEY_STORE], 'readonly');
      
      const photoStore = tx.objectStore(STORE_NAME);
      const keyStore = tx.objectStore(KEY_STORE);
      
      const photosReq = photoStore.getAll();
      const keyReq = keyStore.get('vault-key');
      
      tx.oncomplete = () => {
        const exportData = {
          version: 1,
          exportedAt: Date.now(),
          photos: photosReq.result,
          wrappedKey: keyReq.result
        };
        
        const blob = new Blob([JSON.stringify(exportData)], { type: 'application/json' });
        resolve(blob);
      };
      
      tx.onerror = () => reject(tx.error);
    });
  }, [isUnlocked]);

  // Clear vault (delete all data)
  const clearVault = useCallback(async () => {
    return new Promise((resolve, reject) => {
      const tx = dbRef.current.transaction([STORE_NAME, KEY_STORE], 'readwrite');
      
      tx.objectStore(STORE_NAME).clear();
      tx.objectStore(KEY_STORE).clear();
      
      tx.oncomplete = () => {
        cryptoKeyRef.current = null;
        setIsUnlocked(false);
        setIsInitialized(false);
        setPhotos([]);
        setStorageUsed(0);
        console.log('[Vault] Vault cleared');
        resolve();
      };
      
      tx.onerror = () => reject(tx.error);
    });
  }, []);

  // Check if vault exists
  const checkVaultExists = useCallback(async () => {
    try {
      await initDB();
      const existingKey = await getWrappedKey();
      setIsInitialized(!!existingKey);
      return !!existingKey;
    } catch {
      return false;
    }
  }, [initDB, getWrappedKey]);

  // Initialize on mount
  useEffect(() => {
    checkVaultExists();
  }, [checkVaultExists]);

  const value = {
    // State
    isUnlocked,
    isInitialized,
    photos,
    error,
    storageUsed,
    
    // Actions
    initializeVault,
    lockVault,
    savePhoto,
    loadPhoto,
    deletePhoto,
    exportVault,
    clearVault,
    checkVaultExists,
    
    // Utilities
    formatStorageSize: (bytes) => {
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
  };

  return (
    <VaultContext.Provider value={value}>
      {children}
    </VaultContext.Provider>
  );
}

// Hook to use vault
export function useVault() {
  const context = useContext(VaultContext);
  if (!context) {
    throw new Error('useVault must be used within a VaultProvider');
  }
  return context;
}

export default VaultProvider;
