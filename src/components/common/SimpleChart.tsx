import React, { useState } from 'react';
import type { HourlyStat, MonthlyStat } from '../../types';

interface HourlyChartProps {
  data: HourlyStat[];
  title?: string;
  isDemo?: boolean;
}

export const HourlyDistributionChart: React.FC<HourlyChartProps> = ({ 
  data, 
  title = 'Today\'s Hourly Detection Distribution',
  isDemo = true 
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const maxVal = Math.max(...data.map(d => Math.max(d.detections, d.violations, 1)), 100);

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
          <p className="text-xs text-slate-500">Total vehicles detected vs candidate no-helmet alerts</p>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-xs bg-slate-300"></span>
            <span className="text-slate-600">Total Detections</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-xs bg-red-500"></span>
            <span className="text-slate-600">Safety Candidates</span>
          </div>
          {isDemo && (
            <span className="text-[10px] font-bold uppercase text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
              Demo Data
            </span>
          )}
        </div>
      </div>

      <div className="relative h-56 w-full flex items-end gap-3 pt-6 pb-6 px-2 border-b border-slate-200">
        {data.map((item, index) => {
          const detHeight = Math.round((item.detections / maxVal) * 100);
          const violHeight = Math.round((item.violations / maxVal) * 100);
          const isHovered = hoveredIndex === index;

          return (
            <div 
              key={item.hour}
              className="flex-1 flex flex-col items-center h-full justify-end group cursor-pointer relative"
              onMouseEnter={() => setHoveredIndex(index)}
              onMouseLeave={() => setHoveredIndex(null)}
            >
              {/* Tooltip */}
              {isHovered && (
                <div className="absolute -top-12 z-20 bg-slate-900 text-white text-[11px] py-1.5 px-2.5 rounded-md shadow-md whitespace-nowrap pointer-events-none">
                  <div className="font-semibold text-slate-200">{item.hour}</div>
                  <div className="text-slate-300">Total: {item.detections} | Candidate Alerts: {item.violations}</div>
                </div>
              )}

              {/* Bars side by side */}
              <div className="w-full flex items-end justify-center gap-1.5 h-full">
                {/* Total detections bar */}
                <div 
                  className={`w-1/2 max-w-[20px] rounded-t transition-all ${isHovered ? 'bg-slate-400' : 'bg-slate-200'}`}
                  style={{ height: `${Math.max(detHeight, 6)}%` }}
                />
                {/* Violations bar */}
                <div 
                  className={`w-1/2 max-w-[20px] rounded-t transition-all ${isHovered ? 'bg-red-600' : 'bg-red-500'}`}
                  style={{ height: `${Math.max(violHeight, 6)}%` }}
                />
              </div>

              {/* Hour label */}
              <span className="absolute -bottom-6 text-[11px] font-medium text-slate-500">
                {item.hour}
              </span>
            </div>
          );
        })}
      </div>
      <div className="pt-4 flex justify-between text-xs text-slate-400">
        <span>Morning Shift (06:00 - 12:00)</span>
        <span>Peak Traffic Interval: 09:00 - 10:00 (22 candidate alerts)</span>
      </div>
    </div>
  );
};

interface MonthlyChartProps {
  data: MonthlyStat[];
  title?: string;
  isDemo?: boolean;
}

export const MonthlyTrendChart: React.FC<MonthlyChartProps> = ({ 
  data, 
  title = 'Monthly Enforcement & Compliance Trends',
  isDemo = true 
}) => {
  const [activeItem, setActiveItem] = useState<MonthlyStat | null>(null);

  const maxTotal = Math.max(...data.map(d => d.totalDetections), 40000);

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
          <p className="text-xs text-slate-500">6-Month longitudinal review of camera scans &amp; human-approved drafts</p>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-blue-600"></span>
            <span className="text-slate-600">Approved Drafts</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-slate-300"></span>
            <span className="text-slate-600">Total Scans (k)</span>
          </div>
          {isDemo && (
            <span className="text-[10px] font-bold uppercase text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
              Demo Data
            </span>
          )}
        </div>
      </div>

      {/* Metric summary boxes */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        {data.slice(-3).map(item => (
          <div 
            key={item.month} 
            className={`p-3 rounded-lg border text-left cursor-pointer transition-all ${
              activeItem?.month === item.month ? 'border-blue-500 bg-blue-50/50' : 'border-slate-200 bg-slate-50/60'
            }`}
            onClick={() => setActiveItem(item)}
          >
            <div className="text-xs font-semibold text-slate-600">{item.month}</div>
            <div className="text-base font-bold text-slate-900 mt-0.5">
              {item.approvedDrafts.toLocaleString()} <span className="text-xs font-normal text-slate-500">drafts</span>
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">
              From {(item.totalDetections / 1000).toFixed(1)}k camera scans
            </div>
          </div>
        ))}
      </div>

      {/* SVG Multi-bar representation */}
      <div className="relative h-44 w-full flex items-end gap-4 pt-4 pb-6 px-4 border-b border-slate-200">
        {data.map(item => {
          const scanHeight = Math.round((item.totalDetections / maxTotal) * 100);
          const draftPercent = ((item.approvedDrafts / item.totalDetections) * 100).toFixed(1);

          return (
            <div key={item.month} className="flex-1 flex flex-col items-center h-full justify-end group relative">
              {/* Value label on hover */}
              <div className="text-[10px] font-semibold text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity mb-1">
                {item.approvedDrafts} drafts ({draftPercent}%)
              </div>

              {/* Bar */}
              <div 
                className="w-full max-w-[36px] bg-gradient-to-t from-blue-700 to-blue-500 rounded-t shadow-xs group-hover:from-blue-800 group-hover:to-blue-600 transition-all"
                style={{ height: `${scanHeight}%` }}
              />

              <span className="absolute -bottom-6 text-[11px] font-medium text-slate-500 truncate max-w-full">
                {item.month.split(' ')[0]}
              </span>
            </div>
          );
        })}
      </div>

      <div className="pt-3 flex items-center justify-between text-xs text-slate-500">
        <span>Average human draft validation rate: ~4.9% of candidate alerts</span>
        <span>Rejection rate: ~0.9% (false shadows / occlusion)</span>
      </div>
    </div>
  );
};
