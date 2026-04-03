/**
 * Virtualized Customers Table
 * 
 * Uses @tanstack/react-virtual for efficient rendering of large customer lists.
 * Only renders visible rows + buffer, reducing DOM nodes significantly.
 */
import React, { useRef, useMemo, useCallback } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Checkbox } from '../ui/checkbox';
import { Button } from '../ui/button';
import { Eye } from 'lucide-react';

const ESTIMATED_ROW_HEIGHT = 72;

/**
 * Customer Row Component - Memoized
 */
const CustomerRow = React.memo(({ customer, style, isSelected, onSelect, onView }) => {
  return (
    <div 
      style={style}
      className="absolute left-0 right-0 px-4"
      data-testid={`customer-row-${customer.id}`}
    >
      <div className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors bg-white">
        <div className="flex items-center gap-4">
          <Checkbox 
            checked={isSelected}
            onCheckedChange={(checked) => onSelect(customer.id, checked)}
          />
          <div>
            <p className="font-medium">
              {customer.first_name} {customer.last_name}
            </p>
            <p className="text-sm text-[#5A5A5A]">{customer.email}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="font-medium">${customer.total_spent?.toFixed(2) || '0.00'}</p>
            <p className="text-sm text-[#5A5A5A]">{customer.order_count || 0} orders</p>
          </div>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => onView(customer.id)}
          >
            <Eye className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
});

CustomerRow.displayName = 'CustomerRow';

/**
 * Empty State
 */
const EmptyCustomers = () => (
  <div className="flex flex-col items-center justify-center py-16 text-center">
    <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
      <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    </div>
    <h3 className="text-lg font-medium text-[#2D2A2E] mb-1">No customers found</h3>
    <p className="text-sm text-[#5A5A5A] max-w-xs">
      Customers will appear here when they sign up or make purchases.
    </p>
  </div>
);

/**
 * Skeleton Loader
 */
const CustomersSkeleton = () => (
  <Card style={{ minHeight: '400px' }}>
    <CardHeader>
      <div className="h-6 w-32 bg-gray-200 animate-pulse rounded" />
    </CardHeader>
    <CardContent>
      <div className="space-y-4">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="flex items-center justify-between p-4 border rounded-lg">
            <div className="flex items-center gap-4">
              <div className="h-5 w-5 bg-gray-200 animate-pulse rounded" />
              <div className="space-y-2">
                <div className="h-5 w-32 bg-gray-200 animate-pulse rounded" />
                <div className="h-4 w-48 bg-gray-200 animate-pulse rounded" />
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="space-y-2 text-right">
                <div className="h-5 w-16 bg-gray-200 animate-pulse rounded ml-auto" />
                <div className="h-4 w-20 bg-gray-200 animate-pulse rounded ml-auto" />
              </div>
              <div className="h-8 w-8 bg-gray-200 animate-pulse rounded" />
            </div>
          </div>
        ))}
      </div>
    </CardContent>
  </Card>
);

/**
 * Virtualized Customers Table
 */
const VirtualizedCustomersTable = ({ 
  customers = [], 
  loading = false, 
  selectedCustomers = [],
  onSelectCustomer,
  onViewCustomer,
  maxHeight = 500 
}) => {
  const parentRef = useRef(null);

  const virtualizer = useVirtualizer({
    count: customers.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATED_ROW_HEIGHT,
    overscan: 5,
    paddingStart: 8,
    paddingEnd: 8,
  });

  const handleSelect = useCallback((customerId, checked) => {
    onSelectCustomer(customerId, checked);
  }, [onSelectCustomer]);

  if (loading) {
    return <CustomersSkeleton />;
  }

  if (customers.length === 0) {
    return (
      <Card style={{ minHeight: '300px' }}>
        <CardHeader>
          <CardTitle>All Customers</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyCustomers />
        </CardContent>
      </Card>
    );
  }

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();

  return (
    <Card style={{ minHeight: '400px' }}>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>All Customers</CardTitle>
        <span className="text-sm text-[#5A5A5A]">
          {customers.length} customers
        </span>
      </CardHeader>
      <CardContent className="p-0">
        <div
          ref={parentRef}
          className="overflow-auto"
          style={{ 
            height: Math.min(maxHeight, totalSize + 32),
            contain: 'strict'
          }}
          data-testid="customers-virtual-list"
        >
          <div
            style={{
              height: totalSize,
              width: '100%',
              position: 'relative',
            }}
          >
            {virtualItems.map((virtualRow) => {
              const customer = customers[virtualRow.index];
              return (
                <CustomerRow
                  key={customer.id}
                  customer={customer}
                  style={{
                    height: virtualRow.size,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                  isSelected={selectedCustomers.includes(customer.id)}
                  onSelect={handleSelect}
                  onView={onViewCustomer}
                />
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default VirtualizedCustomersTable;
