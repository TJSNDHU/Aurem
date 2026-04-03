/**
 * Virtualized Products Table
 * 
 * Uses @tanstack/react-virtual for efficient rendering of large product lists.
 * Only renders visible rows + buffer, reducing DOM nodes significantly.
 */
import React, { useRef, useCallback } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Trash2, Plus } from 'lucide-react';

const ESTIMATED_ROW_HEIGHT = 88;

/**
 * Product Row Component - Memoized
 */
const ProductRow = React.memo(({ product, style, onEdit, onDelete }) => {
  return (
    <div 
      style={style}
      className="absolute left-0 right-0 px-4"
      data-testid={`product-row-${product.id}`}
    >
      <div className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors bg-white">
        <div className="flex items-center gap-4">
          <img 
            src={product.images?.[0] || product.image || '/placeholder.jpg'} 
            alt={product.name}
            className="w-16 h-16 object-cover rounded-lg"
            loading="lazy"
          />
          <div>
            <p className="font-medium">{product.name}</p>
            <p className="text-sm text-[#5A5A5A]">${product.price}</p>
            {product.stock !== undefined && (
              <p className="text-xs text-[#8A8A8A]">Stock: {product.stock}</p>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => onEdit(product)}
            data-testid={`edit-product-${product.id}`}
            className="text-[#2D2A2E] border-gray-300 hover:bg-gray-100"
          >
            Edit
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            className="text-red-500 hover:bg-red-50"
            onClick={() => onDelete(product.id)}
            data-testid={`delete-product-${product.id}`}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
});

ProductRow.displayName = 'ProductRow';

/**
 * Empty State
 */
const EmptyProducts = ({ onAdd }) => (
  <div className="flex flex-col items-center justify-center py-16 text-center">
    <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
      <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
    </div>
    <h3 className="text-lg font-medium text-[#2D2A2E] mb-1">No products yet</h3>
    <p className="text-sm text-[#5A5A5A] max-w-xs mb-4">
      Add your first product to start selling.
    </p>
    <Button onClick={onAdd} className="bg-[#2D2A2E] hover:bg-[#3D3A3E]">
      <Plus className="h-4 w-4 mr-2" />
      Add Product
    </Button>
  </div>
);

/**
 * Skeleton Loader
 */
const ProductsSkeleton = () => (
  <Card style={{ minHeight: '500px' }}>
    <CardHeader className="flex flex-row items-center justify-between">
      <div className="h-6 w-24 bg-gray-200 animate-pulse rounded" />
      <div className="h-9 w-28 bg-gray-200 animate-pulse rounded" />
    </CardHeader>
    <CardContent>
      <div className="space-y-4">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="flex items-center justify-between p-4 border rounded-lg">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-gray-200 animate-pulse rounded-lg" />
              <div className="space-y-2">
                <div className="h-5 w-32 bg-gray-200 animate-pulse rounded" />
                <div className="h-4 w-20 bg-gray-200 animate-pulse rounded" />
              </div>
            </div>
            <div className="flex gap-2">
              <div className="h-8 w-16 bg-gray-200 animate-pulse rounded" />
              <div className="h-8 w-8 bg-gray-200 animate-pulse rounded" />
            </div>
          </div>
        ))}
      </div>
    </CardContent>
  </Card>
);

/**
 * Virtualized Products Table
 */
const VirtualizedProductsTable = ({ 
  products = [], 
  loading = false, 
  onEdit,
  onDelete,
  onAdd,
  maxHeight = 500 
}) => {
  const parentRef = useRef(null);

  const virtualizer = useVirtualizer({
    count: products.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATED_ROW_HEIGHT,
    overscan: 5,
    paddingStart: 8,
    paddingEnd: 8,
  });

  const handleEdit = useCallback((product) => {
    onEdit(product);
  }, [onEdit]);

  const handleDelete = useCallback((productId) => {
    onDelete(productId);
  }, [onDelete]);

  if (loading) {
    return <ProductsSkeleton />;
  }

  if (products.length === 0) {
    return (
      <Card style={{ minHeight: '400px' }}>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Products</CardTitle>
          <Button 
            size="sm"
            onClick={onAdd}
            data-testid="add-product-button"
            className="bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Product
          </Button>
        </CardHeader>
        <CardContent>
          <EmptyProducts onAdd={onAdd} />
        </CardContent>
      </Card>
    );
  }

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();

  return (
    <Card style={{ minHeight: '500px' }}>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Products</CardTitle>
        <div className="flex items-center gap-4">
          <span className="text-sm text-[#5A5A5A]">
            {products.length} products
          </span>
          <Button 
            size="sm"
            onClick={onAdd}
            data-testid="add-product-button"
            className="bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Product
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div
          ref={parentRef}
          className="overflow-auto"
          style={{ 
            height: Math.min(maxHeight, totalSize + 32),
            contain: 'strict'
          }}
          data-testid="products-virtual-list"
        >
          <div
            style={{
              height: totalSize,
              width: '100%',
              position: 'relative',
            }}
          >
            {virtualItems.map((virtualRow) => {
              const product = products[virtualRow.index];
              return (
                <ProductRow
                  key={product.id}
                  product={product}
                  style={{
                    height: virtualRow.size,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                />
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default VirtualizedProductsTable;
