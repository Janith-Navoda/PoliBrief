/**
 * PageHeader.jsx
 * Standardized editorial page header component for PoliBrief.
 *
 * Ensures consistent boundaries, typography, badge/eyebrow hierarchy,
 * and responsive action placement across all dashboard pages.
 */
export default function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  className = '',
}) {
  return (
    <div
      className={`flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-[#E5E5E5] ${className}`}
    >
      <div className="space-y-1">
        {eyebrow && (
          <span className="inline-block text-[11px] sm:text-xs font-bold tracking-widest uppercase text-[#767676]">
            {eyebrow}
          </span>
        )}
        <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-[#111111] uppercase leading-tight">
          {title}
        </h1>
        {subtitle && (
          <p className="text-xs sm:text-sm text-[#767676] max-w-3xl leading-relaxed mt-1">
            {subtitle}
          </p>
        )}
      </div>

      {actions && (
        <div className="flex items-center gap-2.5 sm:gap-3 flex-wrap shrink-0 self-start md:self-end">
          {actions}
        </div>
      )}
    </div>
  )
}
