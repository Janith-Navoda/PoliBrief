/**
 * PageContainer.jsx
 * Shared responsive layout container for PoliBrief.
 *
 * Requirements:
 * - Maximum width: ~1440px
 * - Centered using automatic horizontal margins
 * - Consistent horizontal padding: 40px desktop (lg), 24px tablet (sm), 16px mobile
 */
export default function PageContainer({
  children,
  className = '',
  as: Component = 'div',
  ...props
}) {
  return (
    <Component
      className={`w-full max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-10 ${className}`}
      {...props}
    >
      {children}
    </Component>
  )
}
