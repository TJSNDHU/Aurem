/**
 * Admin Dashboard Skeleton Loaders
 * 
 * These skeletons match the exact dimensions of their loaded states
 * to eliminate Cumulative Layout Shift (CLS) on the admin dashboard.
 * 
 * IMPORTANT: min-height values MUST match the loaded component heights
 */
import React from 'react';
import { Card, CardContent, CardHeader } from '../ui/card';

// Skeleton animation class
const skeletonClass = "animate-pulse bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 bg-[length:200%_100%] rounded";

/**
 * Stats Card Skeleton
 * Height: 96px (matches CardContent with pt-6 px-6 and content)
 */
export const StatsCardSkeleton = () => (
  <Card>
    <CardContent className="pt-4 md:pt-6 px-3 md:px-6" style={{ minHeight: '96px' }}>
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className={`h-4 w-16 ${skeletonClass}`} />
          <div className={`h-7 w-20 ${skeletonClass}`} />
        </div>
        <div className={`h-8 w-8 rounded-lg ${skeletonClass}`} />
      </div>
    </CardContent>
  </Card>
);

/**
 * Stats Grid Skeleton (4 cards)
 * Used for the main dashboard stats row
 */
export const StatsGridSkeleton = () => (
  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-6 mb-6">
    <StatsCardSkeleton />
    <StatsCardSkeleton />
    <StatsCardSkeleton />
    <StatsCardSkeleton />
  </div>
);

/**
 * Overview Card Skeleton
 * Height: 280px (matches Overview tab content)
 */
export const OverviewCardSkeleton = () => (
  <Card style={{ minHeight: '280px' }}>
    <CardHeader>
      <div className={`h-6 w-48 ${skeletonClass}`} />
    </CardHeader>
    <CardContent>
      <div className={`h-4 w-full max-w-md ${skeletonClass} mb-6`} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-gray-50 rounded-lg" style={{ minHeight: '72px' }}>
          <div className={`h-5 w-32 ${skeletonClass} mb-2`} />
          <div className={`h-4 w-40 ${skeletonClass}`} />
        </div>
        <div className="p-4 bg-gray-50 rounded-lg" style={{ minHeight: '72px' }}>
          <div className={`h-5 w-28 ${skeletonClass} mb-2`} />
          <div className={`h-4 w-36 ${skeletonClass}`} />
        </div>
      </div>
    </CardContent>
  </Card>
);

/**
 * Single Order Row Skeleton
 * Height: 72px (matches order row with padding)
 */
export const OrderRowSkeleton = () => (
  <div 
    className="flex items-center justify-between p-4 border rounded-lg"
    style={{ minHeight: '72px' }}
  >
    <div className="space-y-2">
      <div className={`h-5 w-32 ${skeletonClass}`} />
      <div className={`h-4 w-48 ${skeletonClass}`} />
    </div>
    <div className="text-right space-y-2">
      <div className={`h-5 w-16 ${skeletonClass} ml-auto`} />
      <div className={`h-5 w-20 ${skeletonClass} ml-auto`} />
    </div>
  </div>
);

/**
 * Orders Table Skeleton
 * Shows 5 skeleton rows (typical above-fold)
 * Height: 540px (5 rows × 72px + header + spacing)
 */
export const OrdersTableSkeleton = () => (
  <Card style={{ minHeight: '540px' }}>
    <CardHeader>
      <div className={`h-6 w-36 ${skeletonClass}`} />
    </CardHeader>
    <CardContent>
      <div className="space-y-4">
        <OrderRowSkeleton />
        <OrderRowSkeleton />
        <OrderRowSkeleton />
        <OrderRowSkeleton />
        <OrderRowSkeleton />
      </div>
    </CardContent>
  </Card>
);

/**
 * Products Grid Skeleton
 * Height: 600px (matches products tab content)
 */
export const ProductsGridSkeleton = () => (
  <Card style={{ minHeight: '600px' }}>
    <CardHeader className="flex flex-row items-center justify-between">
      <div className={`h-6 w-24 ${skeletonClass}`} />
      <div className={`h-9 w-28 ${skeletonClass}`} />
    </CardHeader>
    <CardContent>
      <div className="space-y-4">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="flex items-center gap-4 p-4 border rounded-lg">
            <div className={`h-16 w-16 ${skeletonClass}`} />
            <div className="flex-1 space-y-2">
              <div className={`h-5 w-48 ${skeletonClass}`} />
              <div className={`h-4 w-32 ${skeletonClass}`} />
            </div>
            <div className={`h-8 w-16 ${skeletonClass}`} />
          </div>
        ))}
      </div>
    </CardContent>
  </Card>
);

/**
 * Chart Skeleton
 * For future chart implementations
 * Height: 300px (standard chart height)
 */
export const ChartSkeleton = () => (
  <Card style={{ minHeight: '300px' }}>
    <CardHeader>
      <div className={`h-6 w-32 ${skeletonClass}`} />
    </CardHeader>
    <CardContent className="flex items-center justify-center" style={{ minHeight: '220px' }}>
      <div className="w-full h-48 relative">
        {/* Fake bar chart skeleton */}
        <div className="absolute bottom-0 left-0 right-0 flex items-end justify-between gap-2 h-full px-4">
          {[60, 80, 45, 90, 70, 55, 85].map((height, i) => (
            <div 
              key={i} 
              className={`flex-1 ${skeletonClass}`}
              style={{ height: `${height}%` }}
            />
          ))}
        </div>
      </div>
    </CardContent>
  </Card>
);

/**
 * Full Dashboard Skeleton
 * Shows when entire admin dashboard is loading
 */
export const DashboardSkeleton = () => (
  <div className="space-y-6">
    <StatsGridSkeleton />
    <OverviewCardSkeleton />
  </div>
);

export default {
  StatsCardSkeleton,
  StatsGridSkeleton,
  OverviewCardSkeleton,
  OrderRowSkeleton,
  OrdersTableSkeleton,
  ProductsGridSkeleton,
  ChartSkeleton,
  DashboardSkeleton
};
